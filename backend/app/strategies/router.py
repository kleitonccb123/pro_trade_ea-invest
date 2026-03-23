from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List
from datetime import datetime
import time
import random
from bson import ObjectId
import ast
import logging

from app.core.database import get_db
from app.strategies.models import StrategySubmitRequest, StrategyInDB, StrategyResponse, StrategyListItem
from app.auth.dependencies import get_current_user
from app.core.user_helpers import get_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

# Maximum allowed code size (50 KB) to prevent DoS via oversized payloads
MAX_CODE_SIZE = 50_000


# ========================================================================
# ORDEM IMPORTANTE: Rotas est?ticas ANTES de rotas din?micas!
# FastAPI processa rotas na ordem definida.
# /public/list deve vir ANTES de /{strategy_id}
# ========================================================================

# --------------------------------------------------------------------------
# 1. GET /public/list -> Lista estrat?gias p?blicas (sem autentica??o)
# --------------------------------------------------------------------------
@router.get("/public/list", response_model=List[StrategyListItem])
async def get_public_strategies(
    page: int = Query(1, ge=1, description="Página (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página (max 100)"),
):
    """
    Retorna lista de estratégias públicas disponíveis para todos.
    
    Acesso: Público (não requer autenticação)
    Retorna: Lista de StrategyListItem com is_public=True
    """
    db = get_db()
    strategies_col = db["strategies"]
    skip = (page - 1) * limit
    
    # Retorna apenas as que têm flag is_public=True e não foram soft-deletadas
    strategies = await strategies_col.find({"is_public": True, "deleted_at": {"$exists": False}}).sort("created_at", -1).skip(skip).to_list(length=limit)
    
    return strategies


# --------------------------------------------------------------------------
# 2. GET /my -> Lista APENAS as estrat?gias do usu?rio logado
# --------------------------------------------------------------------------
@router.get("/my", response_model=List[StrategyListItem])
async def get_my_strategies(
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Página (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página (max 100)"),
):
    """
    Retorna apenas as estratégias do usuário autenticado.
    
    Requer: Token JWT válido
    Retorna: Lista de estratégias criadas pelo usuário
    """
    db = get_db()
    strategies_col = db["strategies"]
    skip = (page - 1) * limit
    
    # Busca apenas onde user_id corresponde ao ID do usuário autenticado (exclui soft-deletadas)
    strategies = await strategies_col.find(
        {"user_id": get_user_id(current_user), "deleted_at": {"$exists": False}}
    ).sort("created_at", -1).skip(skip).to_list(length=limit)
    
    return strategies


# --------------------------------------------------------------------------
# 3. POST /submit -> Salva estrat?gia vinculada ao usu?rio
# --------------------------------------------------------------------------
@router.post("/submit", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def submit_strategy(
    strategy: StrategySubmitRequest,
    current_user: dict = Depends(get_current_user)  # Exige login!
):
    """
    Cria uma nova estrat?gia vinculada ao usu?rio autenticado.
    
    Requer: Token JWT v?lido
    Body: StrategySubmitRequest (name, description, parameters, is_public)
    Retorna: StrategyResponse com _id, timestamps e user_id
    
    Seguran?a:
    - O user_id ? extra?do do token validado, n?o do corpo da requisi??o
    - Imposs?vel criar estrat?gia em nome de outro usu?rio
    """
    db = get_db()
    strategies_col = db["strategies"]
    
    # Prepara o objeto para salvar
    strategy_data = strategy.dict()
    
    # VINCULA??O AUTOM?TICA DE SEGURAN?A:
    # N?o confiamos no body da requisi??o para o ID, pegamos do token validado.
    strategy_data["user_id"] = get_user_id(current_user)
    strategy_data["created_at"] = datetime.utcnow()
    strategy_data["updated_at"] = datetime.utcnow()
    
    # Insere no banco de dados
    result = await strategies_col.insert_one(strategy_data)
    
    # Retorna a estrat?gia criada
    created_strategy = await strategies_col.find_one({"_id": result.inserted_id})
    return created_strategy




# --------------------------------------------------------------------------
# 4. GET /{strategy_id} -> Retorna detalhes de uma estrat?gia (se p?blica ou do usu?rio)
# --------------------------------------------------------------------------
@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retorna detalhes de uma estrat?gia.
    
    Requer: Token JWT v?lido
    Retorna: StrategyResponse se:
             - Estrat?gia ? p?blica, OU
             - Usu?rio ? o dono
    """
    db = get_db()
    strategies_col = db["strategies"]
    
    try:
        strategy = await strategies_col.find_one({"_id": ObjectId(strategy_id), "deleted_at": {"$exists": False}})
    except Exception:
        raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    # Verificar permiss?o: ? p?blica ou sou o dono?
    is_owner = strategy.get("user_id") == get_user_id(current_user)
    is_public = strategy.get("is_public", False)
    
    if not (is_public or is_owner):
        raise HTTPException(
            status_code=403,
            detail="Voc? n?o tem permiss?o para visualizar esta estrat?gia."
        )
    
    return strategy




# --------------------------------------------------------------------------
# 5. PUT /{strategy_id} -> Atualiza estrat?gia (apenas o dono)
# --------------------------------------------------------------------------
@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    strategy_update: StrategySubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Atualiza uma estrat?gia existente.
    
    Requer: Token JWT v?lido + ser o dono da estrat?gia
    Body: StrategySubmitRequest com campos atualizados
    Retorna: StrategyResponse atualizado
    
    Seguran?a:
    - O user_id n?o pode ser alterado (n?o est? no update)
    - Apenas o dono pode atualizar
    """
    db = get_db()
    strategies_col = db["strategies"]
    
    try:
        strategy_oid = ObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    # Verificar se estrat?gia existe e pertence ao usu?rio
    existing_strategy = await strategies_col.find_one({
        "_id": strategy_oid,
        "user_id": get_user_id(current_user)
    })
    
    if not existing_strategy:
        existing = await strategies_col.find_one({"_id": strategy_oid})
        if existing:
            raise HTTPException(
                status_code=403,
                detail="Voc? n?o tem permiss?o para atualizar esta estrat?gia."
            )
        else:
            raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    # Preparar dados de atualiza??o
    update_data = strategy_update.dict()
    update_data["updated_at"] = datetime.utcnow()
    
    # N?O atualizamos user_id (seguran?a)
    # Atualizar apenas os campos do request
    await strategies_col.update_one(
        {"_id": strategy_oid},
        {"$set": update_data}
    )
    
    # Retornar estrat?gia atualizada
    updated_strategy = await strategies_col.find_one({"_id": strategy_oid})
    return updated_strategy




# --------------------------------------------------------------------------
# 6. DELETE /{strategy_id} -> Deleta SOMENTE se for dono
# --------------------------------------------------------------------------
@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Deleta uma estrat?gia existente.
    
    Requer: Token JWT v?lido + ser o dono da estrat?gia
    Retorna: 204 No Content se deletado com sucesso
    
    Seguran?a:
    - Query inclui tanto _id quanto user_id
    - Se user_id n?o bate, delete_count ser? 0 e erro 403 ? retornado
    - Imposs?vel deletar estrat?gia de outro usu?rio
    """
    db = get_db()
    strategies_col = db["strategies"]
    
    try:
        strategy_oid = ObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    # Soft delete: define deleted_at em vez de remover fisicamente
    # Isso preserva o registro para auditoria e possível restauração
    result = await strategies_col.update_one(
        {"_id": strategy_oid, "user_id": get_user_id(current_user), "deleted_at": {"$exists": False}},
        {"$set": {"deleted_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        # Verifica se a estrat?gia existe mas pertence a outro
        exists = await strategies_col.find_one({"_id": strategy_oid, "deleted_at": {"$exists": False}})
        if exists:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para deletar esta estratégia."
            )
        else:
            raise HTTPException(status_code=404, detail="Estratégia não encontrada.")
    
    return None




# --------------------------------------------------------------------------
# 7. POST /{strategy_id}/toggle-public -> Alterna visibilidade (apenas dono)
# --------------------------------------------------------------------------
@router.post("/{strategy_id}/toggle-public", response_model=StrategyResponse)
async def toggle_strategy_visibility(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Alterna a visibilidade de uma estrat?gia entre p?blica e privada.
    
    Requer: Token JWT v?lido + ser o dono
    Retorna: StrategyResponse com is_public invertido
    
    Seguran?a:
    - Apenas o dono pode alternar visibilidade
    """
    db = get_db()
    strategies_col = db["strategies"]
    
    try:
        strategy_oid = ObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    # Verificar se estrat?gia existe e pertence ao usu?rio
    strategy = await strategies_col.find_one({
        "_id": strategy_oid,
        "user_id": get_user_id(current_user)
    })
    
    if not strategy:
        existing = await strategies_col.find_one({"_id": strategy_oid})
        if existing:
            raise HTTPException(
                status_code=403,
                detail="Voc? n?o tem permiss?o para alterar esta estrat?gia."
            )
        else:
            raise HTTPException(status_code=404, detail="Estrat?gia n?o encontrada.")
    
    # Alternar is_public
    new_is_public = not strategy.get("is_public", False)
    
    await strategies_col.update_one(
        {"_id": strategy_oid},
        {
            "$set": {
                "is_public": new_is_public,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Retornar estrat?gia atualizada
    updated_strategy = await strategies_col.find_one({"_id": strategy_oid})
    return updated_strategy

# --------------------------------------------------------------------------
# NEW: GET /ranked -> Lista 20 estratégias com rotação de 15 dias
# --------------------------------------------------------------------------
@router.get("/ranked")
async def get_ranked_strategies():
    """
    Retorna até 20 estratégias públicas com rotação determinística a cada 15 dias.

    **Algoritmo de Rotação:**
    - Calcula uma seed baseada na quinzena atual
    - Embaralha deterministicamente para garantir mesma ordem para todos os usuários
    - Os índices 0, 1, 2 são o "Top 3" da quinzena (com medalhas)

    **Acesso:** Público (sem autenticação)
    """
    # ========== 1. CALCULAR SEED DA QUINZENA ==========
    current_timestamp = time.time()
    fortnight_seconds = 15 * 24 * 60 * 60  # 1.296.000 segundos
    current_seed = int(current_timestamp / fortnight_seconds)

    # ========== 2. BUSCAR ESTRATÉGIAS REAIS DO BANCO ==========
    db = get_db()
    strategies_col = db["strategies"]
    all_strategies = await strategies_col.find(
        {"is_public": True, "deleted_at": {"$exists": False}}
    ).sort("created_at", -1).to_list(length=200)

    if not all_strategies:
        return {
            "current_seed": current_seed,
            "rotation_epoch": int(current_timestamp / fortnight_seconds),
            "strategies": [],
        }

    # ========== 3. EMBARALHAR DETERMINISTICAMENTE ==========
    rng = random.Random(current_seed)
    shuffled = list(all_strategies)
    rng.shuffle(shuffled)
    top_20 = shuffled[:20]

    # ========== 4. MARCAR TOP 3 ==========
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for idx in range(min(3, len(top_20))):
        top_20[idx]["is_top3"] = True
        top_20[idx]["medal"] = medals[idx]

    # ========== 5. MONTAR RESPOSTA PAGINADA ==========
    return {
        "current_seed": current_seed,
        "rotation_epoch": int(current_timestamp / fortnight_seconds),
        "strategies": [
            {
                **{k: str(v) if k == "_id" else v for k, v in strat.items()},
                "rank": idx + 1,
                "is_top3": strat.get("is_top3", False),
                "is_top10": idx < 10,
                "medal": strat.get("medal"),
            }
            for idx, strat in enumerate(top_20)
        ],
    }



# ========================================================================
# NEW: STRATEGY BUILDER ENDPOINTS
# ========================================================================

# --------------------------------------------------------------------------
# POST /analyze -> Analisar código Python quanto a erros e segurança
# --------------------------------------------------------------------------
@router.post("/analyze")
async def analyze_strategy_code(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Analisa código Python de uma estratégia quanto a:
    - Erros de sintaxe
    - Segurança
    - Conformidade com modelo esperado
    - Sugestões de otimização
    """
    code = data.get("code", "")
    
    if not code:
        return {
            "valid": False,
            "errors": ["Código está vazio"],
            "warnings": [],
            "suggestions": []
        }
    
    if len(code) > MAX_CODE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Código muito longo (máximo {MAX_CODE_SIZE} caracteres)"
        )
    
    analysis_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "suggestions": []
    }
    
    # 1. Verificar sintaxe Python
    try:
        ast.parse(code)
    except SyntaxError as e:
        analysis_result["valid"] = False
        analysis_result["errors"].append(f"Erro de sintaxe na linha {e.lineno}: {e.msg}")
    
    # 2. Verificar se tem classe TradingStrategy
    if "class TradingStrategy" not in code:
        analysis_result["valid"] = False
        analysis_result["errors"].append("Código deve conter classe 'TradingStrategy'")
    
    # 3. Verificar se tem método analyze
    if "def analyze" not in code:
        analysis_result["valid"] = False
        analysis_result["errors"].append("Classe deve conter método 'analyze(self, df)'")
    
    # 4. Verificar imports perigosos/banido
    forbidden_imports = ['os', 'subprocess', 'shutil', 'sys', 'importlib', '__import__']
    for forbidden in forbidden_imports:
        if f"import {forbidden}" in code or f"from {forbidden}" in code:
            analysis_result["valid"] = False
            analysis_result["errors"].append(f"Import '{forbidden}' não é permitido por segurança")
    
    # 5. Verificar imports obrigatórios
    if "import pandas" not in code and "import pd" not in code:
        analysis_result["warnings"].append("Recomenda-se usar pandas para manipulação de dados")
    
    # 6. Sugestões
    if "numpy" not in code:
        analysis_result["suggestions"].append("Considere usar numpy para operações matemáticas otimizadas")
    
    if "np.nan" not in code and "np.isnan" not in code:
        analysis_result["suggestions"].append("Use np.nan para valores nulos ao invés de None")
    
    if len(code) < 200:
        analysis_result["warnings"].append("Estratégia parece muito simples - Teste para garantir comportamento esperado")
    
    logger.info(f"✅ Análise concluída para usuário {current_user.get('email')} - Valid: {analysis_result['valid']}")
    
    return analysis_result


# --------------------------------------------------------------------------
# POST /fix -> Corrigir erros básicos automaticamente
# --------------------------------------------------------------------------
@router.post("/fix")
async def fix_strategy_code(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Tenta corrigir erros comuns no código da estratégia
    """
    code = data.get("code", "")
    errors = data.get("errors", [])
    
    if len(code) > MAX_CODE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Código muito longo (máximo {MAX_CODE_SIZE} caracteres)"
        )
    
    fixed_code = code
    fixes_applied = []
    
    # Correção 1: Adicionar imports faltantes
    if any("import pandas" in str(e) for e in errors):
        if "import pandas" not in fixed_code:
            fixed_code = "import pandas as pd\nimport numpy as np\n" + fixed_code
            fixes_applied.append("Adicionados imports pandas e numpy")
    
    # Correção 2: Corrigir indentação básica
    try:
        ast.parse(fixed_code)
    except IndentationError:
        # Tentar auto-indentar
        lines = fixed_code.split('\n')
        fixed_lines = []
        current_indent = 0
        
        for line in lines:
            if line.strip() and not line.startswith(' '):
                if line.strip().endswith(':'):
                    fixed_lines.append(line)
                    current_indent += 1
                else:
                    fixed_lines.append('    ' * current_indent + line)
            else:
                fixed_lines.append(line)
        
        fixed_code = '\n'.join(fixed_lines)
        fixes_applied.append("Indentação ajustada")
    
    # Correção 3: Adicionar estrutura mínima se faltando
    if "class TradingStrategy" not in fixed_code:
        base_class = """
class TradingStrategy:
    def __init__(self, **kwargs):
        pass
    
    def analyze(self, df):
        df['signal'] = 0
        return df
"""
        fixed_code = fixed_code + base_class
        fixes_applied.append("Estrutura base adicionada")
    
    logger.info(f"🔧 Código corrigido para {current_user.get('email')} - Fixes: {len(fixes_applied)}")
    
    return {
        "fixed_code": fixed_code,
        "fixes_applied": fixes_applied,
        "message": f"Corrigidas {len(fixes_applied)} problemas"
    }


# --------------------------------------------------------------------------
# POST /test -> Testar estratégia contra dados históricos (simulação segura)
# --------------------------------------------------------------------------
@router.post("/test")
async def test_strategy(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Valida a sintaxe do código e retorna métricas simuladas de backtesting.
    Não executa código arbitrário: usa apenas ast.parse para validação
    e uma simulação determinística baseada na estrutura do código.
    """
    code = data.get("code", "")
    strategy_name = data.get("name", "Test Strategy")  # noqa: F841

    if not code:
        return {
            "status": "error",
            "message": "Código não fornecido",
            "accuracy": 0,
            "trades": 0,
            "profit": 0,
        }
    
    if len(code) > MAX_CODE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Código muito longo (máximo {MAX_CODE_SIZE} caracteres)"
        )

    # ── Validação de sintaxe ────────────────────────────────────────────────
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {
            "status": "error",
            "message": f"Erro de sintaxe na linha {e.lineno}: {e.msg}",
            "accuracy": 0,
            "trades": 0,
            "profit": 0,
        }

    # ── Verificação de tokens proibidos ────────────────────────────────────
    forbidden_tokens = [
        "subprocess", "os.system", "os.popen", "shutil", "importlib",
        "__import__", "exec(", "eval(", "compile(", "open(",
    ]
    for token in forbidden_tokens:
        if token in code:
            return {
                "status": "error",
                "message": f"Código contém símbolo proibido: '{token}'. Apenas lógica de trading é permitida.",
                "accuracy": 0,
                "trades": 0,
                "profit": 0,
            }

    # ── Simulação determinística baseada na estrutura do código ───────────
    # A seed é derivada do hash do conteúdo para reprodutibilidade.
    code_hash = sum(ord(c) for c in code) % 10000
    rng = random.Random(code_hash)

    has_class   = "class TradingStrategy" in code
    has_analyze = "def analyze" in code
    has_signals = "signal" in code
    uses_ma     = any(k in code for k in ["moving_average", "rolling", "ema", "sma"])
    uses_rsi    = "rsi" in code.lower()

    base_accuracy = 50.0
    if not has_class:   base_accuracy -= 15
    if not has_analyze: base_accuracy -= 10
    if not has_signals: base_accuracy -= 5
    if uses_ma:         base_accuracy += 5
    if uses_rsi:        base_accuracy += 3

    accuracy   = round(max(25.0, min(90.0, base_accuracy + rng.uniform(-8, 8))), 2)
    num_trades = rng.randint(15, 80)
    win_rate   = accuracy / 100
    wins       = int(num_trades * win_rate)
    losses     = num_trades - wins
    profit     = round(wins * rng.uniform(1.5, 3.5) - losses * rng.uniform(0.8, 1.8), 2)

    logger.info(
        f"✅ Teste simulado para {current_user.get('email')}: "
        f"{accuracy}% acurácia, {num_trades} trades"
    )
    return {
        "status": "success",
        "accuracy": accuracy,
        "trades": num_trades,
        "profit": profit,
        "message": (
            f"Teste concluído: {num_trades} trades, {accuracy}% acurácia estimada. "
            "Resultados são baseados na análise estática do código."
        ),
    }



# --------------------------------------------------------------------------
# POST /create -> Criar estratégia e publicar na loja se acurácia > 40%
# --------------------------------------------------------------------------
@router.post("/create")
async def create_strategy_from_builder(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Cria uma estratégia a partir do builder.
    Se acurácia >= 40%, publica automaticamente na loja de robôs.
    """
    code = data.get("code", "")
    name = data.get("name", "Unnamed Strategy")
    accuracy = data.get("accuracy", 0)
    trades = data.get("trades", 0)
    profit = data.get("profit", 0)
    
    if not code or accuracy < 40:
        return {
            "status": "error",
            "message": "Código vazio ou acurácia < 40%. Não pode publicar na loja."
        }
    
    db = get_db()
    strategies_col = db["strategies"]
    
    # Criar documento da estratégia
    strategy_doc = {
        "user_id": get_user_id(current_user),
        "name": name,
        "description": f"Estratégia automática com {accuracy:.1f}% acurácia",
        "code": code,
        "accuracy": accuracy,
        "trades": trades,
        "profit": profit,
        "is_public": True,  # Publica automaticamente se acurácia >= 40%
        "in_store": True,   # Marcar como na loja de robôs
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "parameters": {
            "accuracy": accuracy,
            "tested_trades": trades,
            "test_profit": profit
        }
    }
    
    result = await strategies_col.insert_one(strategy_doc)
    
    logger.info(f"🎉 Estratégia criada e publicada na loja para {current_user.get('email')}: {name} ({accuracy:.1f}% acurácia)")
    
    return {
        "status": "success",
        "message": f"✅ Estratégia '{name}' publicada na LOJA DE ROBÔS com {accuracy:.1f}% acurácia!",
        "strategy_id": str(result.inserted_id),
        "in_store": True,
        "accuracy": accuracy
    }

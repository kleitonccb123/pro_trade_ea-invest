from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.database import get_db
from app.strategies.schemas import CodeValidation
from app.strategies.service import StrategySubmissionService

# Request models
class StrategySubmitRequest(BaseModel):
    authorName: str
    email: str
    whatsapp: str
    strategyName: str
    code: str

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


# Rota para validar c?digo
@router.post("/validate", status_code=status.HTTP_200_OK)
async def validate_code(req: CodeValidation):
    """
    Valida se o c?digo Python ? v?lido
    
    Retorna:
        - valid: bool - Se o c?digo ? v?lido
        - error: str - Mensagem de erro (se houver)
    """
    is_valid, error = StrategySubmissionService.validate_python_code(req.code)
    
    return {
        "valid": is_valid,
        "error": error
    }


# Rota para enviar estrat?gia
@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_strategy(req: StrategySubmitRequest):
    """
    Envia uma estrat?gia para armazenamento
    
    Valida o c?digo, salva no MongoDB com expira??o em 50 dias
    """
    try:
        author_name = req.authorName
        email = req.email
        whatsapp = req.whatsapp
        strategy_name = req.strategyName
        code = req.code
        
        # Valida??o b?sica
        if not author_name.strip() or not email.strip() or not whatsapp.strip() or not strategy_name.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Nome do autor, email, WhatsApp e nome da estrat?gia s?o obrigat?rios"
                }
            )
        
        # Validar c?digo
        is_valid, error = StrategySubmissionService.validate_python_code(code)
        if not is_valid:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"C?digo inv?lido: {error}"
                }
            )
        
        # Criar documento
        strategy_doc = StrategySubmissionService.create_strategy_document(
            author_name=author_name,
            email=email,
            whatsapp=whatsapp,
            strategy_name=strategy_name,
            code=code
        )
        
        # Salvar no MongoDB
        try:
            db = get_db()
            collection = db.strategies_submissions
            
            # Criar ?ndice TTL se n?o existir
            await StrategySubmissionService.create_ttl_index(collection)
            
            result = await collection.insert_one(strategy_doc)
            
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": f"Estrat?gia '{strategy_name}' enviada com sucesso!",
                    "strategyId": str(result.inserted_id),
                    "expiresAt": StrategySubmissionService.format_expires_at(strategy_doc["expiresAt"])
                }
            )
        except Exception as db_error:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Erro ao salvar estrat?gia: {str(db_error)}"
                }
            )
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erro ao processar solicita??o: {str(e)}"
            }
        )
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_strategy(
    req: StrategyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new strategy"""
    try:
        # Validate code first
        validation = StrategyValidationService.validate_strategy_code(req.strategy_code)
        if not validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy code: {', '.join(validation.errors)}"
            )

        repo = StrategyRepository(db)
        strategy = await repo.create_strategy(
            user_id=current_user["id"],
            name=req.name,
            description=req.description,
            strategy_code=req.strategy_code,
            symbol=req.symbol,
            timeframe=req.timeframe,
        )

        await db.commit()
        return StrategyResponse.from_db(strategy)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create strategy: {str(e)}"
        )


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all strategies for the current user"""
    try:
        repo = StrategyRepository(db)
        strategies = await repo.get_user_strategies(
            user_id=current_user["id"],
            status=status_filter
        )

        return StrategyListResponse(
            strategies=[StrategyResponse.from_db(s) for s in strategies],
            total=len(strategies)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list strategies: {str(e)}"
        )


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific strategy"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return StrategyResponse.from_db(strategy)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get strategy: {str(e)}"
        )


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    req: StrategyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a strategy"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Validate new code if provided
        if req.strategy_code:
            validation = StrategyValidationService.validate_strategy_code(req.strategy_code)
            if not validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid strategy code: {', '.join(validation.errors)}"
                )

        # Update only provided fields
        update_data = {}
        if req.name is not None:
            update_data["name"] = req.name
        if req.description is not None:
            update_data["description"] = req.description
        if req.strategy_code is not None:
            update_data["strategy_code"] = req.strategy_code
            update_data["version"] = strategy.version + 1
        if req.symbol is not None:
            update_data["symbol"] = req.symbol
        if req.timeframe is not None:
            update_data["timeframe"] = req.timeframe

        updated_strategy = await repo.update_strategy(strategy_id, **update_data)
        await db.commit()

        return StrategyResponse.from_db(updated_strategy)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update strategy: {str(e)}"
        )


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a strategy"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        await repo.delete_strategy(strategy_id)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete strategy: {str(e)}"
        )


@router.post("/{strategy_id}/publish")
async def publish_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Publish strategy to showcase (requires 20+ trades)"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        if strategy.trade_count < 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Strategy must have at least 20 trades to be published. Current: {strategy.trade_count}"
            )

        if strategy.is_expired():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Strategy has expired"
            )

        published_strategy = await repo.publish_strategy(strategy_id)
        await db.commit()

        return PublishStrategyResponse(
            id=published_strategy.id,
            status=published_strategy.status,
            message="Strategy published successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish strategy: {str(e)}"
        )


@router.post("/validate", response_model=StrategyValidationResponse)
async def validate_strategy(req: StrategyValidationRequest):
    """Validate strategy code"""
    try:
        result = StrategyValidationService.validate_strategy_code(req.strategy_code)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )


@router.get("/{strategy_id}/trades")
async def get_strategy_trades(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all trades for a strategy"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        trades = await repo.get_strategy_trades(strategy_id)
        return {
            "trades": [TradeResponse.from_orm(t) for t in trades],
            "total": len(trades)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trades: {str(e)}"
        )


@router.post("/{strategy_id}/bot-instances", response_model=BotInstanceResponse)
async def create_bot_instance(
    strategy_id: int,
    req: BotInstanceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a bot instance for a strategy"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        instance = await repo.create_bot_instance(
            strategy_id=strategy_id,
            symbol=req.symbol,
            timeframe=req.timeframe,
        )

        await db.commit()
        return BotInstanceResponse.from_orm(instance)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bot instance: {str(e)}"
        )


@router.post("/{strategy_id}/bot-instances/{instance_id}/trades", response_model=TradeResponse)
async def add_trade_to_strategy(
    strategy_id: int,
    instance_id: int,
    req: TradeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a trade to a strategy"""
    try:
        repo = StrategyRepository(db)
        strategy = await repo.get_strategy(strategy_id)

        if not strategy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strategy not found"
            )

        if strategy.user_id != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        trade = await repo.add_trade(
            strategy_id=strategy_id,
            instance_id=instance_id,
            entry_price=req.entry_price,
            exit_price=req.exit_price,
            quantity=req.quantity,
            side=req.side,
        )

        await db.commit()
        return TradeResponse.from_orm(trade)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add trade: {str(e)}"
        )
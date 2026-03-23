from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId


# Helper para converter ObjectId para string no Pydantic
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)


# Modelo base para entrada de dados (o que o usu?rio envia)
class StrategySubmitRequest(BaseModel):
    name: str = Field(..., example="Cruzamento de M?dias M?veis")
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(..., example={"short_period": 9, "long_period": 21})
    # NOVO: Define se outros podem ver (padr?o False/Privado)
    is_public: bool = False


# Modelo do que ? salvo no Banco de Dados
class StrategyInDB(StrategySubmitRequest):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    # NOVO: O ID do usu?rio dono desta estrat?gia
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }


# Modelo para resposta ao cliente (o que retornamos)
class StrategyResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    description: Optional[str]
    parameters: Dict[str, Any]
    user_id: str
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }


# Modelo para listagem de estrat?gias (resumido)
class StrategyListItem(BaseModel):
    id: str = Field(alias="_id")
    name: str
    description: Optional[str]
    user_id: str
    is_public: bool
    created_at: datetime

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MacrosOut(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

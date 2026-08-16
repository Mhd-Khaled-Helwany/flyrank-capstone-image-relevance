from __future__ import annotations
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, ValidationError, confloat

class Category(str, Enum):
    animal = "animal"
    plant = "plant"
    vehicle = "vehicle"
    clothing = "clothing"
    furniture = "furniture"
    beverage = "beverage"
    electronic_device = "electronic device"

class Subject(str, Enum):
    bamboo = "bamboo"
    bed = "bed"
    belt = "belt"
    boat = "boat"
    bookshelf = "bookshelf"
    bus = "bus"
    bush = "bush"
    cabinet = "cabinet"
    cactus = "cactus"
    camera = "camera"
    car = "car"
    cat = "cat"
    chair = "chair"
    coffee = "coffee"
    deer = "deer"
    desk = "desk"
    flower = "flower"
    gaming_console = "gaming console"
    gloves = "gloves"
    grass = "grass"
    hat = "hat"
    headphones = "headphones"
    horse = "horse"
    jacket = "jacket"
    juice = "juice"
    laptop = "laptop"
    microphone = "microphone"
    milk = "milk"
    motorcycle = "motorcycle"
    owl = "owl"
    pants = "pants"
    phone = "phone"
    plane = "plane"
    printer = "printer"
    red_fox = "red fox"
    shoes = "shoes"
    smoothie = "smoothie"
    soda = "soda"
    sofa = "sofa"
    squirrel = "squirrel"
    stool = "stool"
    t_shirt = "t-shirt"
    tea = "tea"
    tiger = "tiger"
    train = "train"
    tree = "tree"
    truck = "truck"
    water = "water"
    wheat = "wheat"
    wolf = "wolf"

class TagSchema(BaseModel):
    """Validated schema for a single vision model response."""

    subject: Subject = Field(..., description="Fine-grained subject within a category")
    category: Category = Field(..., description="Broad category (closed vocabulary)")
    attributes: List[str] = Field(default_factory=list, description="Free-text attributes")
    caption: str = Field(..., description="One-sentence caption to embed")
    confidence: confloat(ge=0.0, le=1.0) = Field(..., description="Model confidence 0.0-1.0")

    model_config = {
        "extra": "forbid"
    }

    def needs_review(self, threshold: float = 0.75) -> bool:
        return self.confidence < threshold

def validate_tag_payload(payload: dict) -> tuple[TagSchema | None, dict | None]:
    try:
        tag = TagSchema.model_validate(payload)
        return tag, None
    except ValidationError as exc:
        return None, exc.errors(include_url=False)

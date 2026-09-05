from app.database import Base, engine
from app import models  # noqa: F401  (import so SQLAlchemy sees the model classes)

Base.metadata.create_all(bind=engine)
print("Tables created.")
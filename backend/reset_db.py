from app.database import engine, Base
from app import models

# Drop all tables
Base.metadata.drop_all(bind=engine)
print("Dropped all tables")

# Create all tables
Base.metadata.create_all(bind=engine)
print("Created all tables")
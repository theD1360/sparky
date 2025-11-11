import pytest
from src.database.database import get_database_manager
from src.database.models import Base

@pytest.fixture(scope="session")
def db_manager():
    """Creates a new database manager for a test session."""
    db_url = "sqlite:///:memory:"
    db_manager = get_database_manager(db_url=db_url)
    db_manager.connect()
    Base.metadata.create_all(db_manager.engine)
    yield db_manager
    db_manager.close()

print("conftest loaded")

from uuid import UUID

from app.models import Dataset, Message, MessageRole, Session, User


def test_user_instantiation():
    user = User(email="test@example.com")
    assert user.email == "test@example.com"
    assert isinstance(user.id, UUID)
    assert user.datasets == []


def test_dataset_instantiation():
    dataset = Dataset(
        filename="data.csv",
        original_filename="data.csv",
        storage_path="./data/datasets/1/input.csv",
        domain="finance",
        data_type="time-series",
    )
    assert dataset.filename == "data.csv"
    assert dataset.domain == "finance"
    assert dataset.data_type == "time-series"
    assert isinstance(dataset.id, UUID)
    assert dataset.sessions == []


def test_session_instantiation():
    from decimal import Decimal

    session = Session(dataset_id=UUID(int=0))
    assert session.dataset_id == UUID(int=0)
    assert session.cost_spent == Decimal("0.00")
    assert session.dashboard_path is None
    assert isinstance(session.id, UUID)
    assert session.messages == []


def test_message_instantiation():
    message = Message(
        session_id=UUID(int=0),
        sequence=1,
        role=MessageRole.USER,
        content="Hello",
    )
    assert message.sequence == 1
    assert message.role == MessageRole.USER
    assert message.content == "Hello"
    assert message.metadata_json is None
    assert isinstance(message.id, UUID)

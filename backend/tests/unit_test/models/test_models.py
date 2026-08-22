from uuid import UUID

from app.models import Artifact, Dataset, Message, MessageRole, Session, User


def test_user_instantiation():
    user = User(email="test@example.com")
    assert user.email == "test@example.com"
    assert isinstance(user.id, UUID)
    assert user.datasets == []


def test_dataset_instantiation():
    dataset = Dataset(
        original_filename="data.csv",
        storage_path="./data/datasets/1/input.csv",
        domain="finance",
        data_type="time-series",
    )
    assert dataset.original_filename == "data.csv"
    assert dataset.domain == "finance"
    assert dataset.data_type == "time-series"
    assert isinstance(dataset.id, UUID)
    assert dataset.sessions == []


def test_session_instantiation():
    session = Session(dataset_id=UUID(int=0))
    assert session.dataset_id == UUID(int=0)
    assert isinstance(session.id, UUID)
    assert session.messages == []
    assert session.artifacts == []


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
    assert isinstance(message.id, UUID)


def test_artifact_instantiation():
    artifact = Artifact(
        session_id=UUID(int=0),
        iteration=1,
        hypotheses_evidence_json={"hypotheses": []},
        narrative_json={"summary": "..."},
        dashboard_path="/dashboards/1.html",
    )
    assert artifact.iteration == 1
    assert artifact.hypotheses_evidence_json == {"hypotheses": []}
    assert artifact.narrative_json == {"summary": "..."}
    assert artifact.dashboard_path == "/dashboards/1.html"
    assert isinstance(artifact.id, UUID)

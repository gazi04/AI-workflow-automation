from database import Base, engine
from models import User, UserSettings, Workflow, WorkflowRun, WorkflowLog, WorkflowTemplate, ConnectedAccount

def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    create_tables()

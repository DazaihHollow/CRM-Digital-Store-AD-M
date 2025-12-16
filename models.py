from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Table, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

# Tabla de asociación para Tareas <-> Usuarios (Asignación múltiple)
task_assignments = Table(
    'task_assignments',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('task_id', Integer, ForeignKey('tasks.id'))
)

class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    
    # Relaciones
    created_prospects = relationship("Prospect", back_populates="creator")
    assigned_tasks = relationship("Task", secondary=task_assignments, back_populates="assignees")

class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    industry = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    status = Column(String, default="Nuevo")
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relaciones
    creator = relationship("User", back_populates="created_prospects")
    notes = relationship("Note", back_populates="prospect", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="prospect")

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    prospect_id = Column(Integer, ForeignKey("prospects.id"))

    prospect = relationship("Prospect", back_populates="notes")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    status = Column(String, default=TaskStatus.TODO.value) # todo, in_progress, done
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=True)
    
    # Relaciones
    prospect = relationship("Prospect", back_populates="tasks")
    assignees = relationship("User", secondary=task_assignments, back_populates="assigned_tasks")
    subtasks = relationship("SubTask", back_populates="parent_task", cascade="all, delete-orphan")

class SubTask(Base):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    status = Column(String, default="todo") # todo, in_progress, done
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # FKs
    user_id = Column(Integer, ForeignKey("users.id")) # Es personal del usuario
    task_id = Column(Integer, ForeignKey("tasks.id")) # Vinculada a una tarea padre (asignada)
    
    # Relaciones
    user = relationship("User") # No necesitamos back_populates estricto si no lo usamos
    parent_task = relationship("Task", back_populates="subtasks")

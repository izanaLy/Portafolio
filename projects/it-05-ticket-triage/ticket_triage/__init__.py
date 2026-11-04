"""Ticket Triage Simulator (IT-05): triaje explicable de tickets de soporte."""

from .dataset import Dataset, load_dataset
from .models import Level, Priority, Ticket, TriageResult
from .triage import summarize, triage, triage_all

__all__ = [
    "Dataset",
    "Level",
    "Priority",
    "Ticket",
    "TriageResult",
    "load_dataset",
    "summarize",
    "triage",
    "triage_all",
]

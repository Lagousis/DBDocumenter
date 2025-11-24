"""Datalake synchronization module for DBDocumenter."""

from .azure_storage_adapter import AzureStorageAdapter
from .manager import DatalakeManager

__all__ = ["AzureStorageAdapter", "DatalakeManager"]

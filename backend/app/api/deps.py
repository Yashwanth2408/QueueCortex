from fastapi import Request

from app.config import Settings
from app.sync.manager import SyncManager
from app.trinity_client import TrinityClient


def get_trinity_client(request: Request) -> TrinityClient:
    return request.app.state.trinity_client


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sync_manager(request: Request) -> SyncManager:
    return request.app.state.sync_manager


def get_scheduler(request: Request):
    return request.app.state.scheduler

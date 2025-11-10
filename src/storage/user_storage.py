"""用户数据存储 - JSON文件管理"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..models import BaseDocument, User
from ..models.serialization import DocumentJSONEncoder, to_dict, from_dict
from ..models.user import create_new_user


USER_FILE = Path("/data/disk2/zhz/票据管理比赛/data/user.json")
UPLOADS_DIR = Path("/data/disk2/zhz/票据管理比赛/data/uploads")
DOCUMENTS_DIR = Path("/data/disk2/zhz/票据管理比赛/data/documents")


class UserStorage:
    """用户数据存储管理器
    
    文件结构：
    - data/user.json - 所有用户数据 {"user_id": {...User对象...}}
    - data/uploads/{user_id}/ - 用户上传的图片文件
    """
    
    def __init__(self, user_file: Optional[Path] = None, uploads_dir: Optional[Path] = None, documents_dir: Optional[Path] = None):
        """初始化存储管理器
        
        Args:
            user_file: 用户数据文件路径
            uploads_dir: 上传文件目录
            documents_dir: 文档存储目录
        """
        self.user_file = user_file or USER_FILE
        self.uploads_dir = uploads_dir or UPLOADS_DIR
        self.documents_dir = documents_dir or DOCUMENTS_DIR
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        """确保必要的目录和文件存在"""
        self.user_file.parent.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.user_file.exists():
            # 初始化空的用户数据文件
            with self.user_file.open("w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def _load_all_users(self) -> Dict[str, Dict]:
        """加载所有用户数据"""
        if not self.user_file.exists():
            return {}
        
        with self.user_file.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
    
    def _save_all_users(self, users_data: Dict[str, Dict]) -> None:
        """保存所有用户数据"""
        with self.user_file.open("w", encoding="utf-8") as f:
            json.dump(users_data, f, cls=DocumentJSONEncoder, ensure_ascii=False, indent=2)
    
    def get_user_upload_dir(self, user_id: str) -> Path:
        """获取用户上传文件目录"""
        user_upload_dir = self.uploads_dir / user_id
        user_upload_dir.mkdir(parents=True, exist_ok=True)
        return user_upload_dir
    
    def save_user(self, user: User) -> None:
        """保存用户数据到JSON
        
        Args:
            user: 用户对象
        """
        all_users = self._load_all_users()
        user_data = to_dict(user)
        all_users[user.user_id] = user_data
        self._save_all_users(all_users)
    
    def load_user(self, user_id: str) -> Optional[User]:
        """从JSON加载用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户对象，如果不存在返回None
        """
        all_users = self._load_all_users()
        user_data = all_users.get(user_id)
        
        if not user_data:
            return None
        
        return from_dict(user_data, User)
    
    def user_exists(self, user_id: str) -> bool:
        """检查用户是否存在
        
        Args:
            user_id: 用户ID
            
        Returns:
            True如果用户存在
        """
        all_users = self._load_all_users()
        return user_id in all_users
    
    def delete_user(self, user_id: str) -> bool:
        """删除用户及其所有数据
        
        Args:
            user_id: 用户ID
            
        Returns:
            True如果删除成功
        """
        all_users = self._load_all_users()
        
        if user_id not in all_users:
            return False
        
        del all_users[user_id]
        self._save_all_users(all_users)
        
        # 删除用户上传文件目录
        user_upload_dir = self.uploads_dir / user_id
        if user_upload_dir.exists():
            import shutil
            shutil.rmtree(user_upload_dir)
        
        return True
    
    def create_user_if_not_exists(self, user_id: str, profile_items: Optional[List[str]] = None) -> User:
        """如果用户不存在则创建
        
        Args:
            user_id: 用户ID
            profile_items: 初始画像条目
            
        Returns:
            用户对象
        """
        user = self.load_user(user_id)
        if user:
            return user
        
        # 创建新用户
        user = create_new_user(user_id, profile_items)
        self.save_user(user)
        return user
    
    def list_all_users(self) -> List[str]:
        """列出所有用户ID
        
        Returns:
            用户ID列表
        """
        all_users = self._load_all_users()
        return list(all_users.keys())
    
    def get_user_document_count(self, user_id: str) -> int:
        """获取用户票据数量
        
        Args:
            user_id: 用户ID
            
        Returns:
            票据数量
        """
        user = self.load_user(user_id)
        if not user:
            return 0
        return len(user.document_ids)
    
    def get_user_documents_dir(self, user_id: str) -> Path:
        """获取用户文档存储目录
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户文档目录路径
        """
        user_docs_dir = self.documents_dir / user_id
        user_docs_dir.mkdir(parents=True, exist_ok=True)
        return user_docs_dir
    
    def save_document(self, user_id: str, document: BaseDocument) -> None:
        """保存票据到JSON文件
        
        Args:
            user_id: 用户ID
            document: 票据对象
        """
        user_docs_dir = self.get_user_documents_dir(user_id)
        doc_file = user_docs_dir / f"{document.document_id}.json"
        
        doc_data = to_dict(document)
        with doc_file.open("w", encoding="utf-8") as f:
            json.dump(doc_data, f, cls=DocumentJSONEncoder, ensure_ascii=False, indent=2)
    
    def load_document(self, user_id: str, document_id: str) -> Optional[BaseDocument]:
        """从JSON文件加载票据
        
        Args:
            user_id: 用户ID
            document_id: 票据ID
            
        Returns:
            票据对象，如果不存在返回None
        """
        user_docs_dir = self.get_user_documents_dir(user_id)
        doc_file = user_docs_dir / f"{document_id}.json"
        
        if not doc_file.exists():
            return None
        
        with doc_file.open("r", encoding="utf-8") as f:
            doc_data = json.load(f)
        
        return from_dict(doc_data, BaseDocument)
    
    def list_user_documents(self, user_id: str) -> List[str]:
        """列出用户的所有票据ID
        
        Args:
            user_id: 用户ID
            
        Returns:
            票据ID列表
        """
        user_docs_dir = self.get_user_documents_dir(user_id)
        if not user_docs_dir.exists():
            return []
        
        doc_ids = []
        for doc_file in user_docs_dir.glob("*.json"):
            doc_id = doc_file.stem
            doc_ids.append(doc_id)
        
        return doc_ids


__all__ = ["UserStorage"]


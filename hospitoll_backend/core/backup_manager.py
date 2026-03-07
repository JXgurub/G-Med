"""
Backup and Recovery System
Automated database and file backups with restore functionality
"""

import os
import json
import zipfile
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from celery import shared_task

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages database and file backups"""
    
    BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')
    
    def __init__(self):
        self._ensure_backup_dir()
    
    @staticmethod
    def _ensure_backup_dir():
        """Create backup directory if it doesn't exist"""
        os.makedirs(BackupManager.BACKUP_DIR, exist_ok=True)
    
    @staticmethod
    def create_database_backup(backup_name: Optional[str] = None) -> dict:
        """
        Create a database backup
        
        Args:
            backup_name: Custom backup name (optional)
            
        Returns:
            dict: Backup info including path and size
        """
        try:
            if not backup_name:
                backup_name = f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = os.path.join(BackupManager.BACKUP_DIR, f"{backup_name}.sql")
            
            if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
                # SQLite backup - simple copy
                db_file = settings.DATABASES['default']['NAME']
                shutil.copy2(db_file, backup_path)
                logger.info(f"SQLite backup created: {backup_path}")
            
            elif settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
                # PostgreSQL backup
                db_config = settings.DATABASES['default']
                backup_path = os.path.join(BackupManager.BACKUP_DIR, f"{backup_name}.dump")
                
                dump_command = [
                    'pg_dump',
                    f"--host={db_config.get('HOST', 'localhost')}",
                    f"--port={db_config.get('PORT', 5432)}",
                    f"--username={db_config['USER']}",
                    f"--dbname={db_config['NAME']}",
                    f"--file={backup_path}",
                    '--format=plain'
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = db_config['PASSWORD']
                
                subprocess.run(dump_command, env=env, check=True)
                logger.info(f"PostgreSQL backup created: {backup_path}")
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            
            backup_info = {
                'name': backup_name,
                'path': backup_path,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'timestamp': datetime.now().isoformat(),
                'type': 'database'
            }
            
            return backup_info
        
        except Exception as e:
            logger.error(f"Error creating database backup: {str(e)}")
            raise
    
    @staticmethod
    def create_media_backup(backup_name: Optional[str] = None) -> dict:
        """
        Create a backup of media files
        
        Args:
            backup_name: Custom backup name (optional)
            
        Returns:
            dict: Backup info
        """
        try:
            if not backup_name:
                backup_name = f"media_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_zip = os.path.join(BackupManager.BACKUP_DIR, f"{backup_name}.zip")
            media_root = settings.MEDIA_ROOT
            
            if not os.path.exists(media_root):
                logger.warning(f"Media directory not found: {media_root}")
                return {'error': 'Media directory not found'}
            
            with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, media_root)
                        zipf.write(file_path, arcname)
            
            file_size = os.path.getsize(backup_zip)
            
            backup_info = {
                'name': backup_name,
                'path': backup_zip,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'timestamp': datetime.now().isoformat(),
                'type': 'media'
            }
            
            logger.info(f"Media backup created: {backup_zip}")
            return backup_info
        
        except Exception as e:
            logger.error(f"Error creating media backup: {str(e)}")
            raise
    
    @staticmethod
    def create_full_backup(backup_name: Optional[str] = None) -> dict:
        """
        Create a full backup (database + media)
        
        Args:
            backup_name: Custom backup name (optional)
            
        Returns:
            dict: Full backup info
        """
        try:
            if not backup_name:
                backup_name = f"full_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"Starting full backup: {backup_name}")
            
            # Create database backup
            db_backup = BackupManager.create_database_backup(f"{backup_name}_db")
            
            # Create media backup
            media_backup = BackupManager.create_media_backup(f"{backup_name}_media")
            
            # Create manifest
            manifest = {
                'backup_name': backup_name,
                'timestamp': datetime.now().isoformat(),
                'database': db_backup,
                'media': media_backup,
                'django_version': __import__('django').get_version(),
                'python_version': __import__('sys').version,
            }
            
            manifest_path = os.path.join(
                BackupManager.BACKUP_DIR,
                f"{backup_name}_manifest.json"
            )
            
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"Full backup completed: {backup_name}")
            
            return {
                'name': backup_name,
                'manifest_path': manifest_path,
                'database': db_backup,
                'media': media_backup,
                'total_size_mb': db_backup['size_mb'] + media_backup['size_mb'],
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error creating full backup: {str(e)}")
            raise
    
    @staticmethod
    def list_backups(backup_type: Optional[str] = None) -> list:
        """
        List available backups
        
        Args:
            backup_type: Filter by type ('database', 'media', 'full', None for all)
            
        Returns:
            list: List of backup info dicts
        """
        backups = []
        
        for filename in sorted(os.listdir(BackupManager.BACKUP_DIR), reverse=True):
            if filename.endswith('_manifest.json'):
                manifest_path = os.path.join(BackupManager.BACKUP_DIR, filename)
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    
                    if backup_type is None or backup_type == 'full':
                        backups.append(manifest)
                
                except Exception as e:
                    logger.error(f"Error reading manifest {filename}: {str(e)}")
        
        return backups
    
    @staticmethod
    def delete_old_backups(retention_days: int = 30):
        """
        Delete backups older than retention period
        
        Args:
            retention_days: Number of days to retain backups
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0
            
            for filename in os.listdir(BackupManager.BACKUP_DIR):
                file_path = os.path.join(BackupManager.BACKUP_DIR, filename)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_mtime < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {filename}")
            
            logger.info(f"Cleanup completed. Deleted {deleted_count} old backups.")
            
        except Exception as e:
            logger.error(f"Error deleting old backups: {str(e)}")
    
    @staticmethod
    def restore_database_backup(backup_name: str) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_name: Name of the backup to restore
            
        Returns:
            bool: Success status
        """
        try:
            backup_path = os.path.join(BackupManager.BACKUP_DIR, f"{backup_name}.sql")
            
            if not os.path.exists(backup_path):
                backup_path = os.path.join(BackupManager.BACKUP_DIR, f"{backup_name}.dump")
            
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_name}")
                return False
            
            if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
                # SQLite restore
                db_file = settings.DATABASES['default']['NAME']
                shutil.copy2(backup_path, db_file)
                logger.info(f"SQLite database restored from: {backup_path}")
            
            elif settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
                # PostgreSQL restore
                db_config = settings.DATABASES['default']
                
                restore_command = [
                    'psql',
                    f"--host={db_config.get('HOST', 'localhost')}",
                    f"--port={db_config.get('PORT', 5432)}",
                    f"--username={db_config['USER']}",
                    f"--dbname={db_config['NAME']}",
                    f"--file={backup_path}"
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = db_config['PASSWORD']
                
                subprocess.run(restore_command, env=env, check=True)
                logger.info(f"PostgreSQL database restored from: {backup_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error restoring database: {str(e)}")
            raise


# Celery tasks for automated backups
@shared_task
def create_daily_backup():
    """
    Create daily full backup (automated via Celery Beat)
    """
    try:
        backup_info = BackupManager.create_full_backup()
        logger.info(f"Daily backup completed: {json.dumps(backup_info)}")
        
        # Cleanup old backups
        BackupManager.delete_old_backups(retention_days=30)
        
        return {'status': 'success', 'backup': backup_info}
    
    except Exception as e:
        logger.error(f"Daily backup failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


@shared_task
def create_weekly_backup():
    """
    Create weekly full backup for archival
    """
    try:
        backup_name = f"weekly_backup_{datetime.now().strftime('%Y_W%W')}"
        backup_info = BackupManager.create_full_backup(backup_name)
        logger.info(f"Weekly backup completed: {json.dumps(backup_info)}")
        return {'status': 'success', 'backup': backup_info}
    
    except Exception as e:
        logger.error(f"Weekly backup failed: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

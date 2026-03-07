"""
Django management command for creating database backups
Usage: python manage.py backup --full
"""

from django.core.management.base import BaseCommand
from core.backup_manager import BackupManager
import json


class Command(BaseCommand):
    help = 'Create database and media backups'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Create full backup (database + media)',
        )
        parser.add_argument(
            '--db-only',
            action='store_true',
            help='Create database backup only',
        )
        parser.add_argument(
            '--media-only',
            action='store_true',
            help='Create media backup only',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available backups',
        )
        parser.add_argument(
            '--cleanup',
            type=int,
            metavar='DAYS',
            help='Delete backups older than specified days',
        )
    
    def handle(self, *args, **options):
        if options['list']:
            self.list_backups()
        elif options['cleanup']:
            self.cleanup_backups(options['cleanup'])
        elif options['full']:
            self.create_full_backup()
        elif options['db_only']:
            self.create_db_backup()
        elif options['media_only']:
            self.create_media_backup()
        else:
            self.stdout.write(
                self.style.WARNING('No backup option specified. Use --help for more info.')
            )
    
    def create_full_backup(self):
        """Create full backup"""
        self.stdout.write('Creating full backup...')
        try:
            backup_info = BackupManager.create_full_backup()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Full backup created successfully!")
            )
            self.stdout.write(f"  Name: {backup_info['name']}")
            self.stdout.write(f"  Total size: {backup_info['total_size_mb']} MB")
            self.stdout.write(f"  Database: {backup_info['database']['size_mb']} MB")
            self.stdout.write(f"  Media: {backup_info['media']['size_mb']} MB")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error creating backup: {str(e)}")
            )
    
    def create_db_backup(self):
        """Create database backup only"""
        self.stdout.write('Creating database backup...')
        try:
            backup_info = BackupManager.create_database_backup()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Database backup created successfully!")
            )
            self.stdout.write(f"  Name: {backup_info['name']}")
            self.stdout.write(f"  Size: {backup_info['size_mb']} MB")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error creating backup: {str(e)}")
            )
    
    def create_media_backup(self):
        """Create media backup only"""
        self.stdout.write('Creating media backup...')
        try:
            backup_info = BackupManager.create_media_backup()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Media backup created successfully!")
            )
            self.stdout.write(f"  Name: {backup_info['name']}")
            self.stdout.write(f"  Size: {backup_info['size_mb']} MB")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error creating backup: {str(e)}")
            )
    
    def list_backups(self):
        """List all available backups"""
        self.stdout.write('Available backups:')
        try:
            backups = BackupManager.list_backups()
            if not backups:
                self.stdout.write(self.style.WARNING('No backups found.'))
                return
            
            for backup in backups:
                self.stdout.write(f"\n  📦 {backup['backup_name']}")
                self.stdout.write(f"     Timestamp: {backup['timestamp']}")
                
                if 'database' in backup:
                    db_size = backup['database'].get('size_mb', 0)
                    self.stdout.write(f"     Database: {db_size} MB")
                
                if 'media' in backup:
                    media_size = backup['media'].get('size_mb', 0)
                    self.stdout.write(f"     Media: {media_size} MB")
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error listing backups: {str(e)}")
            )
    
    def cleanup_backups(self, days):
        """Delete old backups"""
        self.stdout.write(f'Deleting backups older than {days} days...')
        try:
            BackupManager.delete_old_backups(days)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Cleanup completed!")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error during cleanup: {str(e)}")
            )

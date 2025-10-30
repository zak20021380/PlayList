# database.py - Database Management
# مدیریت دیتابیس

import copy
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import *
from utils import calculate_score


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.data = self.load_data()

    def load_data(self) -> Dict:
        """Load database from JSON file"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return self._ensure_structure(data)
            except Exception:
                return self._create_empty_db()
        return self._create_empty_db()

    def _ensure_structure(self, data: Dict) -> Dict:
        """Ensure new keys exist in old database files"""
        if 'premium_plans' not in data:
            data['premium_plans'] = copy.deepcopy(DEFAULT_PREMIUM_PLANS)

        data.setdefault('song_daily_likes', {})
        data.setdefault('last_top_song_broadcast', None)

        moods = data.get('moods')
        if not isinstance(moods, dict) or not moods:
            data['moods'] = copy.deepcopy(DEFAULT_MOODS)
        else:
            data['moods'] = dict(moods)

        # Update users with new premium fields if missing
        for user in data.get('users', {}).values():
            user.setdefault('premium_plan_id', None)
            user.setdefault('premium_price', 0)
            user.setdefault('active_playlist_id', None)
            user.setdefault('total_adds', 0)
            user.setdefault('added_playlists', [])
            user.setdefault('last_seen', user.get('join_date', datetime.now().isoformat()))
            user.setdefault('pending_payment', None)

        # Update playlists with new fields
        users = data.get('users', {})

        for playlist in data.get('playlists', {}).values():
            status = playlist.setdefault('status', 'draft')
            owner_id = str(playlist.get('owner_id', ''))
            owner = users.get(owner_id)
            default_limit = (
                PREMIUM_SONGS_PER_PLAYLIST if owner and owner.get('premium') else FREE_SONGS_PER_PLAYLIST
            )
            if default_limit and default_limit > 0:
                playlist['max_songs'] = default_limit
            else:
                playlist['max_songs'] = 0
            playlist.setdefault('published_at', None)
            playlist.setdefault('is_private', False)
            if status not in ('draft', 'published'):
                playlist['status'] = 'draft'
            if playlist['status'] == 'draft' and len(playlist.get('songs', [])) >= MIN_SONGS_TO_PUBLISH:
                playlist['status'] = 'published'

        for song in data.get('songs', {}).values():
            song.setdefault('channel_message_id', None)
            song.setdefault('storage_channel_id', STORAGE_CHANNEL_ID)
            song.setdefault('likes', [])
            song.setdefault('original_song_id', song.get('id'))
            song.setdefault('added_from_playlist_id', None)
            song.setdefault('added_by', None)
            song.setdefault('uploader_id', song.get('uploader_id'))
            song.setdefault('uploader_name', song.get('uploader_name'))

        return data

    def _create_empty_db(self) -> Dict:
        """Create empty database structure"""
        return {
            'users': {},
            'playlists': {},
            'songs': {},
            'moods': copy.deepcopy(DEFAULT_MOODS),
            'stats': {
                'total_plays': 0,
                'total_likes': 0,
                'total_users': 0,
            },
            'premium_plans': copy.deepcopy(DEFAULT_PREMIUM_PLANS),
            'song_daily_likes': {},
            'last_top_song_broadcast': None,
        }

    def save_data(self):
        """Save database to JSON file"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ===== USER MANAGEMENT =====

    def create_user(self, user_id: int, username: str, first_name: str) -> Dict:
        """Create new user"""
        user_id = str(user_id)
        if user_id in self.data['users']:
            return self.data['users'][user_id]

        user = {
            'user_id': user_id,
            'username': username or 'بدون_یوزرنیم',
            'first_name': first_name,
            'playlists': [],
            'liked_playlists': [],
            'added_playlists': [],
            'following': [],
            'followers': [],
            'badges': [],
            'premium': False,
            'premium_until': None,
            'premium_plan_id': None,
            'premium_price': 0,
            'banned': False,
            'total_plays': 0,
            'total_likes_received': 0,
            'total_songs_uploaded': 0,
            'total_adds': 0,
            'notifications_enabled': True,
            'join_date': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'active_playlist_id': None,
            'pending_payment': None,
        }

        self.data['users'][user_id] = user
        self.data['stats']['total_users'] += 1
        self.save_data()
        return user

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        return self.data['users'].get(str(user_id))

    def update_user(self, user_id: int, updates: Dict):
        """Update user data"""
        user_id = str(user_id)
        if user_id in self.data['users']:
            self.data['users'][user_id].update(updates)
            self.save_data()

    def touch_user(self, user_id: int):
        """Update user's last seen timestamp"""
        user = self.get_user(user_id)
        if not user:
            return

        now = datetime.now()
        last_seen_raw = user.get('last_seen')

        try:
            last_seen_dt = datetime.fromisoformat(last_seen_raw) if last_seen_raw else None
        except Exception:
            last_seen_dt = None

        if last_seen_dt and (now - last_seen_dt).total_seconds() < 60:
            return

        user['last_seen'] = now.isoformat()
        self.save_data()

    def is_premium(self, user_id: int) -> bool:
        """Check if user is premium"""
        user = self.get_user(user_id)
        if not user or not user.get('premium'):
            return False

        # Check if premium expired
        if user.get('premium_until'):
            expiry = datetime.fromisoformat(user['premium_until'])
            if datetime.now() > expiry:
                self.update_user(user_id, {'premium': False})
                self.apply_free_limits(user_id)
                return False
        return True

    def activate_premium(
        self,
        user_id: int,
        days: Optional[int] = None,
        plan_id: Optional[str] = None,
        price: Optional[int] = None,
    ):
        """Activate premium for user"""
        if days is None:
            if plan_id:
                plan = self.get_premium_plan(plan_id)
                days = plan.get('duration_days') if plan else 30
            else:
                days = 30

        if price is None:
            if plan_id:
                plan = self.get_premium_plan(plan_id)
                price = plan.get('price') if plan else 0
            else:
                price = 0

        expiry = datetime.now() + timedelta(days=days)
        self.update_user(user_id, {
            'premium': True,
            'premium_until': expiry.isoformat(),
            'premium_plan_id': plan_id,
            'premium_price': price,
            'pending_payment': None,
        })
        self.apply_premium_limits(user_id)
        # Give premium badge
        self.add_badge(user_id, 'premium')

    def _apply_playlist_song_limits(self, user: Dict, target_limit: int):
        """Apply song limit to all playlists owned by user"""
        if user is None:
            return

        limit_value = target_limit if target_limit and target_limit > 0 else 0
        updated = False

        for playlist_id in user.get('playlists', []):
            playlist = self.get_playlist(playlist_id)
            if not playlist:
                continue

            current_limit = playlist.get('max_songs', 0) or 0

            if limit_value == 0:
                if current_limit != 0:
                    playlist['max_songs'] = 0
                    updated = True
            elif current_limit != limit_value:
                playlist['max_songs'] = limit_value
                updated = True

        if updated:
            self.save_data()

    def apply_premium_limits(self, user_id: int):
        """Ensure premium users have enforced limits on existing playlists"""
        user = self.get_user(user_id)
        if not user:
            return

        self._apply_playlist_song_limits(user, PREMIUM_SONGS_PER_PLAYLIST)

    def apply_free_limits(self, user_id: int):
        """Ensure free users respect the standard limits"""
        user = self.get_user(user_id)
        if not user:
            return

        self._apply_playlist_song_limits(user, FREE_SONGS_PER_PLAYLIST)

    def set_pending_payment(
        self,
        user_id: int,
        *,
        authority: str,
        amount: int,
        plan_id: str,
        title: str,
        duration_days: int,
    ):
        """Persist pending payment data for user"""
        user = self.get_user(user_id)
        if not user:
            return

        user['pending_payment'] = {
            'authority': authority,
            'amount': amount,
            'plan_id': plan_id,
            'title': title,
            'duration_days': duration_days,
            'created_at': datetime.now().isoformat(),
        }
        self.save_data()

    def clear_pending_payment(self, user_id: int):
        """Remove pending payment info for user"""
        user = self.get_user(user_id)
        if not user:
            return

        if user.get('pending_payment') is not None:
            user['pending_payment'] = None
            self.save_data()

    # ===== PREMIUM PLANS =====

    def get_premium_plans(self) -> List[Dict]:
        """Return list of premium plans"""
        return self.data.get('premium_plans', [])

    def get_premium_plan(self, plan_id: str) -> Optional[Dict]:
        """Return single premium plan by id"""
        for plan in self.get_premium_plans():
            if plan.get('id') == plan_id:
                return plan
        return None

    def add_premium_plan(self, title: str, price: int, duration_days: int) -> Dict:
        """Add new premium plan"""
        plan = {
            'id': uuid.uuid4().hex[:8],
            'title': title,
            'price': price,
            'duration_days': duration_days,
        }
        self.data.setdefault('premium_plans', []).append(plan)
        self.save_data()
        return plan

    def update_premium_plan(self, plan_id: str, **updates):
        """Update existing premium plan"""
        plan = self.get_premium_plan(plan_id)
        if not plan:
            return
        plan.update(updates)
        self.save_data()

    def delete_premium_plan(self, plan_id: str):
        """Delete premium plan"""
        plans = self.get_premium_plans()
        updated = [plan for plan in plans if plan.get('id') != plan_id]
        if len(updated) != len(plans):
            self.data['premium_plans'] = updated
            self.save_data()

    def ban_user(self, user_id: int):
        """Ban user"""
        self.update_user(user_id, {'banned': True})

    def unban_user(self, user_id: int):
        """Unban user"""
        self.update_user(user_id, {'banned': False})

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        user = self.get_user(user_id)
        return user.get('banned', False) if user else False

    # ===== PLAYLIST MANAGEMENT =====

    def create_playlist(self, user_id: int, name: str, mood: str = 'happy') -> Optional[str]:
        """Create new playlist"""
        user = self.get_user(user_id)
        if not user:
            return None

        # Check limit
        is_prem = self.is_premium(user_id)
        limit = PREMIUM_PLAYLIST_LIMIT if is_prem else FREE_PLAYLIST_LIMIT
        if limit and limit > 0 and len(user['playlists']) >= limit:
            return None

        # Generate playlist ID
        playlist_id = f"pl_{user_id}_{len(self.data['playlists'])}"

        max_songs = (
            PREMIUM_SONGS_PER_PLAYLIST if is_prem else FREE_SONGS_PER_PLAYLIST
        )

        available_moods = self.data.get('moods', {})
        if mood not in available_moods:
            fallback_mood = next(iter(available_moods.keys()), None)
            mood = fallback_mood or 'happy'

        playlist = {
            'id': playlist_id,
            'name': name,
            'owner_id': str(user_id),
            'owner_name': user['first_name'],
            'mood': mood,
            'songs': [],
            'likes': [],
            'plays': 0,
            'created_at': datetime.now().isoformat(),
            'is_private': False,
            'status': 'draft',
            'max_songs': max_songs,
            'published_at': None,
        }

        self.data['playlists'][playlist_id] = playlist
        user['playlists'].append(playlist_id)
        user['active_playlist_id'] = playlist_id
        self.save_data()

        # Check for first playlist badge
        if len(user['playlists']) == 1:
            self.add_badge(user_id, 'first_playlist')

        return playlist_id

    def get_playlist(self, playlist_id: str) -> Optional[Dict]:
        """Get playlist by ID"""
        return self.data['playlists'].get(playlist_id)

    def get_moods(self) -> Dict[str, str]:
        """Return available playlist moods/categories"""
        moods = self.data.get('moods') or {}
        if not isinstance(moods, dict):
            return dict(copy.deepcopy(DEFAULT_MOODS))
        return dict(moods)

    def get_default_mood(self) -> str:
        """Return default mood key used for new playlists"""
        moods = self.get_moods()
        if moods:
            return next(iter(moods.keys()))
        return 'happy'

    def add_mood(self, key: str, title: str) -> Tuple[bool, str]:
        """Add a new playlist category"""
        moods = self.data.setdefault('moods', {})

        normalized_key = key.strip().lower()
        normalized_key = re.sub(r"\s+", "_", normalized_key)

        if not normalized_key or not re.fullmatch(r"[a-z0-9_]+", normalized_key):
            return False, 'invalid_key'

        display_title = title.strip()
        if not display_title:
            return False, 'invalid_title'

        if normalized_key in moods:
            return False, 'exists'

        moods[normalized_key] = display_title
        self.save_data()
        return True, normalized_key

    def delete_mood(self, key: str) -> Tuple[bool, str]:
        """Delete mood and return fallback mood key"""
        moods = self.data.get('moods', {})

        if key not in moods:
            return False, 'not_found'

        if len(moods) <= 1:
            return False, 'last_one'

        fallback_key = None
        for candidate in moods.keys():
            if candidate != key:
                fallback_key = candidate
                break

        for playlist in self.data.get('playlists', {}).values():
            if playlist.get('mood') == key:
                playlist['mood'] = fallback_key

        moods.pop(key)
        self.save_data()
        return True, fallback_key or ''

    def delete_playlist(self, playlist_id: str) -> List[Tuple[int, int]]:
        """Delete playlist and return storage channel messages to remove"""
        deleted_messages: List[Tuple[int, int]] = []

        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return deleted_messages

        user_id = playlist['owner_id']
        user = self.get_user(int(user_id)) if user_id else None

        # Collect songs for cleanup
        for song_id in list(playlist.get('songs', [])):
            song = self.data['songs'].get(song_id)
            if not song:
                continue

            channel_message_id = song.get('channel_message_id')
            storage_channel_id = song.get('storage_channel_id', STORAGE_CHANNEL_ID)

            if (
                channel_message_id
                and self._is_channel_message_unique(song_id, storage_channel_id, channel_message_id)
            ):
                channel_id_int = int(storage_channel_id) if storage_channel_id is not None else STORAGE_CHANNEL_ID
                deleted_messages.append((channel_id_int, int(channel_message_id)))

            # Remove song entry
            del self.data['songs'][song_id]

        if user and playlist_id in user['playlists']:
            user['playlists'].remove(playlist_id)
            if user.get('active_playlist_id') == playlist_id:
                user['active_playlist_id'] = self._find_fallback_playlist_id(int(user_id))

        del self.data['playlists'][playlist_id]
        self.save_data()

        return deleted_messages

    def _is_channel_message_unique(
        self,
        song_id: str,
        storage_channel_id: Optional[int],
        channel_message_id: Optional[int],
    ) -> bool:
        """Check if the forwarded message is only used by the given song"""
        if channel_message_id is None:
            return False

        for other_song_id, other_song in self.data.get('songs', {}).items():
            if other_song_id == song_id:
                continue

            other_channel_id = other_song.get('storage_channel_id', STORAGE_CHANNEL_ID)
            other_message_id = other_song.get('channel_message_id')

            if (
                other_channel_id == storage_channel_id
                and other_message_id == channel_message_id
            ):
                return False

        return True

    def get_user_playlists(self, user_id: int) -> List[Dict]:
        """Get all playlists of a user"""
        user = self.get_user(user_id)
        if not user:
            return []
        drafts = []
        published = []
        for pl_id in user['playlists']:
            playlist = self.get_playlist(pl_id)
            if not playlist:
                continue
            if playlist.get('status') != 'published' and playlist.get('owner_id') != str(user_id):
                continue
            if playlist.get('status') == 'published':
                published.append(playlist)
            else:
                drafts.append(playlist)

        return drafts + published

    def set_playlist_visibility(self, user_id: int, playlist_id: str, is_private: bool) -> bool:
        """Update playlist visibility if the requesting user is the owner"""
        playlist = self.get_playlist(playlist_id)
        if not playlist or playlist.get('owner_id') != str(user_id):
            return False

        playlist['is_private'] = bool(is_private)
        self.save_data()
        return True

    def toggle_playlist_visibility(self, user_id: int, playlist_id: str) -> Optional[bool]:
        """Toggle playlist visibility and return the new state"""
        playlist = self.get_playlist(playlist_id)
        if not playlist or playlist.get('owner_id') != str(user_id):
            return None

        new_state = not playlist.get('is_private', False)
        playlist['is_private'] = new_state
        self.save_data()
        return new_state

    def _find_fallback_playlist_id(self, user_id: int) -> Optional[str]:
        """Return the most recent playlist id for user"""
        user = self.get_user(user_id)
        if not user:
            return None
        for pl_id in reversed(user.get('playlists', [])):
            playlist = self.get_playlist(pl_id)
            if playlist and playlist.get('owner_id') == str(user_id):
                return pl_id
        return None

    def get_active_playlist(self, user_id: int) -> Optional[Dict]:
        """Return user's active playlist if available"""
        user = self.get_user(user_id)
        if not user:
            return None

        playlist_id = user.get('active_playlist_id')
        if playlist_id:
            playlist = self.get_playlist(playlist_id)
            if playlist and playlist.get('owner_id') == str(user_id):
                return playlist

        fallback_id = self._find_fallback_playlist_id(user_id)
        if fallback_id:
            return self.get_playlist(fallback_id)
        return None

    def set_active_playlist(self, user_id: int, playlist_id: Optional[str]):
        """Persist user's active playlist"""
        user = self.get_user(user_id)
        if not user:
            return

        if playlist_id:
            playlist = self.get_playlist(playlist_id)
            if not playlist or playlist.get('owner_id') != str(user_id):
                return

        user['active_playlist_id'] = playlist_id
        self.save_data()

    def add_song_to_playlist(self, playlist_id: str, song_data: Dict) -> Tuple[bool, str]:
        """Add song to playlist"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False, 'playlist_not_found'

        max_songs = playlist.get('max_songs', 0) or 0
        current_count = len(playlist.get('songs', []))
        if max_songs and current_count >= max_songs:
            return False, 'playlist_full'

        if not song_data.get('channel_message_id'):
            return False, 'storage_missing'

        song_data['channel_message_id'] = int(song_data['channel_message_id'])

        # Generate song ID
        song_id = f"song_{len(self.data['songs'])}"
        song_data['id'] = song_id
        song_data['playlist_id'] = playlist_id
        song_data['uploaded_at'] = datetime.now().isoformat()
        song_data.setdefault('storage_channel_id', STORAGE_CHANNEL_ID)
        song_data.setdefault('likes', [])
        song_data.setdefault('original_song_id', song_id)
        song_data.setdefault('added_from_playlist_id', None)
        song_data.setdefault('added_by', str(playlist.get('owner_id')))
        song_data.setdefault('uploader_id', str(song_data.get('uploader_id') or playlist.get('owner_id')))
        song_data.setdefault('uploader_name', song_data.get('uploader_name') or playlist.get('owner_name'))

        self.data['songs'][song_id] = song_data
        playlist['songs'].append(song_id)

        owner_id = int(playlist['owner_id'])

        # Update user stats
        user = self.get_user(owner_id)
        if user:
            user['total_songs_uploaded'] += 1

            # Check badges
            if user['total_songs_uploaded'] >= 100:
                self.add_badge(owner_id, 'music_lover')

        # Auto-publish if minimum songs reached
        current_count += 1
        message_key = 'song_added'
        if playlist.get('status') != 'published':
            if current_count >= MIN_SONGS_TO_PUBLISH:
                playlist['status'] = 'published'
                playlist['published_at'] = datetime.now().isoformat()
                message_key = 'playlist_published'
            else:
                message_key = 'draft_progress'

        self.save_data()
        return True, message_key

    # ===== LIKES & INTERACTIONS =====

    def publish_playlist(self, playlist_id: str) -> bool:
        """Force publish a playlist manually"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False

        if playlist.get('status') == 'published':
            return False

        playlist['status'] = 'published'
        playlist['published_at'] = datetime.now().isoformat()
        self.save_data()
        return True

    def like_playlist(self, user_id: int, playlist_id: str) -> bool:
        """Like a playlist"""
        playlist = self.get_playlist(playlist_id)
        user = self.get_user(user_id)

        if not playlist or not user:
            return False

        user_id_str = str(user_id)

        # Check if already liked
        if user_id_str in playlist.get('likes', []):
            return False

        # Add like
        if 'likes' not in playlist:
            playlist['likes'] = []
        playlist['likes'].append(user_id_str)

        # Add to user's liked playlists
        if playlist_id not in user['liked_playlists']:
            user['liked_playlists'].append(playlist_id)

        # Update owner stats
        owner = self.get_user(int(playlist['owner_id']))
        if owner:
            owner['total_likes_received'] += 1

            # Check badges
            total_likes = owner['total_likes_received']
            if total_likes >= 100 and 'popular' not in owner['badges']:
                self.add_badge(int(playlist['owner_id']), 'popular')

        self.data['stats']['total_likes'] += 1
        self.save_data()
        return True

    def unlike_playlist(self, user_id: int, playlist_id: str) -> bool:
        """Unlike a playlist"""
        playlist = self.get_playlist(playlist_id)
        user = self.get_user(user_id)

        if not playlist or not user:
            return False

        user_id_str = str(user_id)

        if user_id_str in playlist.get('likes', []):
            playlist['likes'].remove(user_id_str)

        if playlist_id in user['liked_playlists']:
            user['liked_playlists'].remove(playlist_id)

        # Update owner stats
        owner = self.get_user(int(playlist['owner_id']))
        if owner and owner['total_likes_received'] > 0:
            owner['total_likes_received'] -= 1

        self.save_data()
        return True

    def like_song(self, user_id: int, song_id: str) -> bool:
        """Register a like for a song"""
        song = self.data['songs'].get(song_id)
        user = self.get_user(user_id)

        if not song or not user:
            return False

        user_id_str = str(user_id)
        likes = song.setdefault('likes', [])

        if user_id_str in likes:
            return False

        likes.append(user_id_str)

        self._record_song_daily_like(song_id)

        uploader_id = song.get('uploader_id')
        if uploader_id:
            owner = self.get_user(int(uploader_id))
            if owner is not None:
                owner['total_likes_received'] += 1

        self.save_data()
        return True

    def unlike_song(self, user_id: int, song_id: str) -> bool:
        """Remove like from a song"""
        song = self.data['songs'].get(song_id)
        user = self.get_user(user_id)

        if not song or not user:
            return False

        user_id_str = str(user_id)
        likes = song.setdefault('likes', [])

        if user_id_str not in likes:
            return False

        likes.remove(user_id_str)

        uploader_id = song.get('uploader_id')
        if uploader_id:
            owner = self.get_user(int(uploader_id))
            if owner is not None and owner['total_likes_received'] > 0:
                owner['total_likes_received'] -= 1

        self.save_data()
        return True

    def _record_song_daily_like(self, song_id: Optional[str], date: Optional[str] = None):
        """Increment daily like counter for a song"""
        if not song_id:
            return

        date_str = date or datetime.now().strftime('%Y-%m-%d')
        daily_likes = self.data.setdefault('song_daily_likes', {})
        day_bucket = daily_likes.setdefault(date_str, {})
        day_bucket[song_id] = day_bucket.get(song_id, 0) + 1

        self._prune_song_daily_likes()

    def _prune_song_daily_likes(self, retention_days: int = 14):
        """Remove outdated daily like entries to keep database small"""
        daily_likes = self.data.get('song_daily_likes', {})
        if not daily_likes:
            return

        cutoff_date = datetime.now().date() - timedelta(days=retention_days)

        for date_key in list(daily_likes.keys()):
            try:
                day_date = datetime.strptime(date_key, '%Y-%m-%d').date()
            except ValueError:
                continue

            if day_date < cutoff_date:
                daily_likes.pop(date_key, None)

    def get_top_song_of_day(self, date: Optional[str] = None) -> Tuple[Optional[Dict], int]:
        """Return the most liked song for the specified day"""
        target_date = date or datetime.now().strftime('%Y-%m-%d')
        daily_likes = self.data.get('song_daily_likes', {})
        day_bucket = daily_likes.get(target_date, {})

        if not day_bucket:
            return None, 0

        # Sort by likes descending
        sorted_entries = sorted(day_bucket.items(), key=lambda item: item[1], reverse=True)

        for song_id, like_count in sorted_entries:
            song = self.data['songs'].get(song_id)
            if song and like_count > 0:
                return song, like_count

        return None, 0

    def get_last_top_song_broadcast(self) -> Optional[str]:
        """Return the date string of the last daily top song broadcast"""
        return self.data.get('last_top_song_broadcast')

    def set_last_top_song_broadcast(self, date: str):
        """Persist the date string of the latest daily top song broadcast"""
        self.data['last_top_song_broadcast'] = date
        self.save_data()

    def user_has_song_copy(self, user_id: int, original_song_id: str) -> bool:
        """Check if user already saved a copy of the song"""
        user = self.get_user(user_id)
        if not user:
            return False

        for playlist_id in user.get('playlists', []):
            playlist = self.get_playlist(playlist_id)
            if not playlist:
                continue

            for song_id in playlist.get('songs', []):
                song = self.data['songs'].get(song_id)
                if not song:
                    continue
                if song.get('original_song_id', song.get('id')) == original_song_id:
                    return True

        return False

    def add_existing_song_to_playlist(
        self,
        source_song_id: str,
        target_playlist_id: str,
        actor_id: int,
    ) -> Tuple[bool, str]:
        """Clone an existing song into the user's playlist"""

        source_song = self.data['songs'].get(source_song_id)
        target_playlist = self.get_playlist(target_playlist_id)
        actor = self.get_user(actor_id)

        if not source_song or not target_playlist or not actor:
            return False, 'not_found'

        if target_playlist.get('owner_id') != str(actor_id):
            return False, 'not_owner'

        max_songs = target_playlist.get('max_songs', 0) or 0
        if max_songs and len(target_playlist.get('songs', [])) >= max_songs:
            return False, 'playlist_full'

        # Prevent duplicates
        signature = (
            source_song.get('storage_channel_id'),
            source_song.get('channel_message_id'),
        )

        for existing_song_id in target_playlist.get('songs', []):
            existing_song = self.data['songs'].get(existing_song_id)
            if not existing_song:
                continue
            existing_signature = (
                existing_song.get('storage_channel_id'),
                existing_song.get('channel_message_id'),
            )
            if existing_signature == signature:
                return False, 'duplicate'

        new_song_id = f"song_{len(self.data['songs'])}"
        cloned_song = {
            'id': new_song_id,
            'title': source_song.get('title'),
            'performer': source_song.get('performer'),
            'duration': source_song.get('duration'),
            'file_size': source_song.get('file_size'),
            'channel_message_id': source_song.get('channel_message_id'),
            'storage_channel_id': source_song.get('storage_channel_id', STORAGE_CHANNEL_ID),
            'playlist_id': target_playlist_id,
            'uploaded_at': datetime.now().isoformat(),
            'likes': [],
            'original_song_id': source_song.get('original_song_id', source_song_id),
            'added_from_playlist_id': source_song.get('playlist_id'),
            'added_by': str(actor_id),
            'uploader_id': source_song.get('uploader_id'),
            'uploader_name': source_song.get('uploader_name'),
        }

        self.data['songs'][new_song_id] = cloned_song
        target_playlist.setdefault('songs', []).append(new_song_id)

        actor['total_adds'] += 1

        source_playlist_id = source_song.get('playlist_id')
        if source_playlist_id:
            source_playlist = self.get_playlist(source_playlist_id)
            if source_playlist and source_playlist.get('owner_id') != str(actor_id):
                added_playlists = actor.setdefault('added_playlists', [])
                if source_playlist_id not in added_playlists:
                    added_playlists.append(source_playlist_id)

        self.save_data()
        return True, 'added'

    def remove_song_from_playlist(
        self,
        playlist_id: str,
        song_id: str,
        actor_id: int,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Remove a song from a playlist if the actor owns it"""

        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False, {'status': 'playlist_not_found'}

        if playlist.get('owner_id') != str(actor_id):
            return False, {'status': 'not_owner'}

        if song_id not in playlist.get('songs', []):
            return False, {'status': 'song_not_in_playlist'}

        song = self.data['songs'].get(song_id)
        storage_messages: List[Tuple[int, int]] = []

        if song:
            channel_message_id = song.get('channel_message_id')
            storage_channel_id = song.get('storage_channel_id', STORAGE_CHANNEL_ID)

            if (
                channel_message_id
                and self._is_channel_message_unique(song_id, storage_channel_id, channel_message_id)
            ):
                channel_id_int = int(storage_channel_id) if storage_channel_id is not None else STORAGE_CHANNEL_ID
                storage_messages.append((channel_id_int, int(channel_message_id)))

        playlist['songs'] = [sid for sid in playlist.get('songs', []) if sid != song_id]

        actor = self.get_user(actor_id)
        if actor and song:
            added_from_playlist_id = song.get('added_from_playlist_id')
            added_by = song.get('added_by')

            if added_from_playlist_id and added_by == str(actor_id):
                actor['total_adds'] = max(0, actor.get('total_adds', 0) - 1)

                still_has_copy = False
                for owned_playlist_id in actor.get('playlists', []):
                    owned_playlist = self.get_playlist(owned_playlist_id)
                    if not owned_playlist:
                        continue

                    for owned_song_id in owned_playlist.get('songs', []):
                        owned_song = self.data['songs'].get(owned_song_id)
                        if owned_song and owned_song.get('added_from_playlist_id') == added_from_playlist_id:
                            still_has_copy = True
                            break

                    if still_has_copy:
                        break

                if not still_has_copy:
                    added_playlists = actor.setdefault('added_playlists', [])
                    if added_from_playlist_id in added_playlists:
                        added_playlists.remove(added_from_playlist_id)
            elif added_by == str(actor_id):
                actor['total_songs_uploaded'] = max(0, actor.get('total_songs_uploaded', 0) - 1)

        playlist_was_published = playlist.get('status') == 'published'
        remaining_songs = len(playlist.get('songs', []))
        playlist_now_draft = False

        if playlist_was_published and remaining_songs < MIN_SONGS_TO_PUBLISH:
            playlist['status'] = 'draft'
            playlist['published_at'] = None
            playlist_now_draft = True

        if song_id in self.data['songs']:
            del self.data['songs'][song_id]

        self.save_data()

        return True, {
            'status': 'removed',
            'storage_messages': storage_messages,
            'playlist_now_draft': playlist_now_draft,
            'remaining_songs': remaining_songs,
            'max_songs': playlist.get('max_songs', 0) or 0,
        }

    def get_user_added_playlists(self, user_id: int) -> List[Dict]:
        """Return playlists that user has saved songs from"""
        user = self.get_user(user_id)
        if not user:
            return []

        playlists: List[Dict] = []
        seen = set()

        for playlist_id in user.get('added_playlists', []):
            if playlist_id in seen:
                continue

            playlist = self.get_playlist(playlist_id)
            if not playlist:
                continue

            playlists.append(playlist)
            seen.add(playlist_id)

        return playlists

    def count_song_adds(self, original_song_id: Optional[str]) -> int:
        """Return number of times a song has been saved to other playlists"""
        if not original_song_id:
            return 0

        count = 0

        for song in self.data.get('songs', {}).values():
            if song.get('original_song_id') != original_song_id:
                continue

            if song.get('id') == original_song_id:
                continue

            count += 1

        return count

    def increment_plays(self, playlist_id: str):
        """Increment play count"""
        playlist = self.get_playlist(playlist_id)
        if playlist:
            playlist['plays'] = playlist.get('plays', 0) + 1

            # Update owner stats
            owner = self.get_user(int(playlist['owner_id']))
            if owner:
                owner['total_plays'] += 1

                # Check viral badge
                if playlist['plays'] >= 1000 and 'viral' not in owner['badges']:
                    self.add_badge(int(playlist['owner_id']), 'viral')

            self.data['stats']['total_plays'] += 1
            self.save_data()

    # ===== FOLLOW SYSTEM =====

    def follow_user(self, follower_id: int, following_id: int) -> bool:
        """Follow a user"""
        follower = self.get_user(follower_id)
        following = self.get_user(following_id)

        if not follower or not following or follower_id == following_id:
            return False

        following_id_str = str(following_id)
        follower_id_str = str(follower_id)

        # Check if already following
        if following_id_str in follower['following']:
            return False

        # Check follow limit
        is_prem = self.is_premium(follower_id)
        limit = PREMIUM_FOLLOW_LIMIT if is_prem else FREE_FOLLOW_LIMIT
        if len(follower['following']) >= limit:
            return False

        follower['following'].append(following_id_str)
        following['followers'].append(follower_id_str)

        self.save_data()
        return True

    def unfollow_user(self, follower_id: int, following_id: int) -> bool:
        """Unfollow a user"""
        follower = self.get_user(follower_id)
        following = self.get_user(following_id)

        if not follower or not following:
            return False

        following_id_str = str(following_id)
        follower_id_str = str(follower_id)

        if following_id_str in follower['following']:
            follower['following'].remove(following_id_str)

        if follower_id_str in following['followers']:
            following['followers'].remove(follower_id_str)

        self.save_data()
        return True

    # ===== BADGES =====

    def add_badge(self, user_id: int, badge_name: str):
        """Add badge to user"""
        user = self.get_user(user_id)
        if user and badge_name in BADGES and badge_name not in user['badges']:
            user['badges'].append(badge_name)
            self.save_data()

    # ===== LEADERBOARD =====

    def get_leaderboard(self, sort_by='likes', limit=20) -> List[Dict]:
        """Get leaderboard with detailed ranking data"""
        users: List[Dict] = []

        for user_id, user in self.data['users'].items():
            if user.get('banned'):
                continue

            likes = user.get('total_likes_received', 0)
            plays = user.get('total_plays', 0)
            songs = user.get('total_songs_uploaded', 0)
            playlists_count = len(user.get('playlists', []))
            followers_count = len(user.get('followers', []))
            join_date_raw = user.get('join_date')

            try:
                join_timestamp = datetime.fromisoformat(join_date_raw).timestamp() if join_date_raw else float('inf')
            except Exception:
                join_timestamp = float('inf')

            composite_score = calculate_score(user)

            if sort_by == 'likes':
                primary_metric = likes
            elif sort_by == 'plays':
                primary_metric = plays
            elif sort_by == 'songs':
                primary_metric = songs
            else:
                primary_metric = composite_score

            first_name = user.get('first_name') or ''
            username = user.get('username') or ''

            if first_name and first_name.lower() != 'unknown':
                display_name = first_name
            elif username:
                display_name = f"@{username}"
            else:
                display_name = f"کاربر {user_id[-4:]}"

            users.append({
                'user_id': user_id,
                'name': display_name,
                'username': username,
                'score': composite_score,
                'likes': likes,
                'plays': plays,
                'songs': songs,
                'playlists': playlists_count,
                'followers': followers_count,
                'is_premium': user.get('premium', False),
                '_primary_metric': primary_metric,
                '_join_timestamp': join_timestamp,
            })

        users.sort(
            key=lambda x: (
                -x['_primary_metric'],
                -x['score'],
                -x['likes'],
                -x['plays'],
                -x['songs'],
                -x['followers'],
                x['_join_timestamp'],
            )
        )

        for user in users:
            user.pop('_primary_metric', None)
            user.pop('_join_timestamp', None)

        if limit is None or limit <= 0:
            return users

        return users[:limit]

    # ===== BROWSE & DISCOVER =====

    def get_all_playlists(self, filter_private=True) -> List[Dict]:
        """Get all public playlists"""
        playlists = []
        for pl_id, playlist in self.data['playlists'].items():
            if filter_private and playlist.get('is_private'):
                continue
            if playlist.get('status') != 'published':
                continue
            playlists.append(playlist)
        return playlists

    def get_trending_playlists(self, days=7, limit=20) -> List[Dict]:
        """Get trending playlists"""
        cutoff = datetime.now() - timedelta(days=days)
        playlists = []

        for playlist in self.get_all_playlists():
            created = datetime.fromisoformat(playlist['created_at'])
            if created > cutoff:
                playlists.append(playlist)

        playlists.sort(key=lambda x: x.get('plays', 0), reverse=True)
        return playlists[:limit]

    def get_top_playlists(self, limit=20) -> List[Dict]:
        """Get top playlists by likes"""
        playlists = self.get_all_playlists()
        playlists.sort(key=lambda x: len(x.get('likes', [])), reverse=True)
        return playlists[:limit]

    def get_new_playlists(self, limit=20) -> List[Dict]:
        """Get newest playlists"""
        playlists = self.get_all_playlists()

        def _created_at(playlist):
            created = playlist.get('created_at')
            try:
                return datetime.fromisoformat(created)
            except Exception:
                return datetime.min

        playlists.sort(key=_created_at, reverse=True)
        return playlists[:limit]

    def get_playlists_by_mood(self, mood: str, limit=20) -> List[Dict]:
        """Get playlists filtered by mood"""
        playlists = [
            playlist
            for playlist in self.get_all_playlists()
            if playlist.get('mood') == mood
        ]
        playlists.sort(key=lambda x: len(x.get('likes', [])), reverse=True)
        return playlists[:limit]

    def search_playlists(self, query: str) -> List[Dict]:
        """Search playlists by name"""
        query = query.lower()
        results = []
        for playlist in self.get_all_playlists():
            if query in playlist['name'].lower():
                results.append(playlist)
        return results

    # ===== STATS =====

    def get_global_stats(self) -> Dict:
        """Get global statistics"""
        total_playlists = len(
            [
                pl
                for pl in self.data['playlists'].values()
                if pl.get('status') == 'published'
            ]
        )
        total_songs = len(self.data['songs'])
        users = list(self.data['users'].values())
        total_users = len(users)
        banned_users = len([u for u in users if u.get('banned')])
        active_users = total_users - banned_users

        today = datetime.now().date()
        seven_days_ago = today - timedelta(days=6)

        new_today = 0
        new_last_week = 0
        active_today = 0
        premium_users = 0
        revenue = 0
        premium_status_changed = False

        for user in users:
            if user.get('banned'):
                continue

            join_date_raw = user.get('join_date')
            last_seen_raw = user.get('last_seen')

            try:
                join_date = datetime.fromisoformat(join_date_raw).date() if join_date_raw else None
            except Exception:
                join_date = None

            try:
                last_seen = datetime.fromisoformat(last_seen_raw).date() if last_seen_raw else None
            except Exception:
                last_seen = None

            if join_date:
                if join_date == today:
                    new_today += 1
                if join_date >= seven_days_ago:
                    new_last_week += 1

            if last_seen and last_seen == today:
                active_today += 1

            if user.get('premium'):
                premium_until_raw = user.get('premium_until')
                has_active_premium = True

                if premium_until_raw:
                    try:
                        expiry = datetime.fromisoformat(premium_until_raw)
                        if datetime.now() > expiry:
                            has_active_premium = False
                    except Exception:
                        has_active_premium = False

                if has_active_premium:
                    premium_users += 1
                    revenue += user.get('premium_price', 0) or 0
                else:
                    user['premium'] = False
                    premium_status_changed = True

        if premium_status_changed:
            self.save_data()

        return {
            'total_users': total_users,
            'active_users': active_users,
            'banned_users': banned_users,
            'active_today': active_today,
            'new_today': new_today,
            'new_last_week': new_last_week,
            'total_playlists': total_playlists,
            'total_songs': total_songs,
            'total_likes': self.data['stats']['total_likes'],
            'total_plays': self.data['stats']['total_plays'],
            'premium_users': premium_users,
            'premium_ratio': (premium_users / active_users) if active_users else 0,
            'revenue': revenue,
        }

    def get_user_rank(self, user_id: int, sort_by: str = 'likes') -> int:
        """Get user rank in leaderboard"""
        leaderboard = self.get_leaderboard(sort_by=sort_by, limit=0)
        user_id_str = str(user_id)

        for i, user in enumerate(leaderboard, 1):
            if user['user_id'] == user_id_str:
                return i
        return 0


# Initialize database
db = Database()

# database.py - Database Management
# مدیریت دیتابیس

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import *


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.data = self.load_data()

    def load_data(self) -> Dict:
        """Load database from JSON file"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._create_empty_db()
        return self._create_empty_db()

    def _create_empty_db(self) -> Dict:
        """Create empty database structure"""
        return {
            'users': {},
            'playlists': {},
            'songs': {},
            'moods': DEFAULT_MOODS,
            'stats': {
                'total_plays': 0,
                'total_likes': 0,
                'total_users': 0,
            }
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
            'following': [],
            'followers': [],
            'badges': [],
            'premium': False,
            'premium_until': None,
            'banned': False,
            'total_plays': 0,
            'total_likes_received': 0,
            'total_songs_uploaded': 0,
            'notifications_enabled': True,
            'join_date': datetime.now().isoformat(),
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
                return False
        return True

    def activate_premium(self, user_id: int, days: int = PREMIUM_DURATION_DAYS):
        """Activate premium for user"""
        expiry = datetime.now() + timedelta(days=days)
        self.update_user(user_id, {
            'premium': True,
            'premium_until': expiry.isoformat()
        })
        # Give premium badge
        self.add_badge(user_id, 'premium')

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
        if len(user['playlists']) >= limit:
            return None

        # Generate playlist ID
        playlist_id = f"pl_{user_id}_{len(self.data['playlists'])}"

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
        }

        self.data['playlists'][playlist_id] = playlist
        user['playlists'].append(playlist_id)
        self.save_data()

        # Check for first playlist badge
        if len(user['playlists']) == 1:
            self.add_badge(user_id, 'first_playlist')

        return playlist_id

    def get_playlist(self, playlist_id: str) -> Optional[Dict]:
        """Get playlist by ID"""
        return self.data['playlists'].get(playlist_id)

    def delete_playlist(self, playlist_id: str):
        """Delete playlist"""
        playlist = self.get_playlist(playlist_id)
        if playlist:
            user_id = playlist['owner_id']
            user = self.get_user(int(user_id))
            if user and playlist_id in user['playlists']:
                user['playlists'].remove(playlist_id)
            del self.data['playlists'][playlist_id]
            self.save_data()

    def get_user_playlists(self, user_id: int) -> List[Dict]:
        """Get all playlists of a user"""
        user = self.get_user(user_id)
        if not user:
            return []
        return [self.get_playlist(pl_id) for pl_id in user['playlists'] if self.get_playlist(pl_id)]

    def add_song_to_playlist(self, playlist_id: str, song_data: Dict) -> bool:
        """Add song to playlist"""
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            return False

        # Generate song ID
        song_id = f"song_{len(self.data['songs'])}"
        song_data['id'] = song_id
        song_data['playlist_id'] = playlist_id
        song_data['uploaded_at'] = datetime.now().isoformat()

        self.data['songs'][song_id] = song_data
        playlist['songs'].append(song_id)

        # Update user stats
        owner_id = int(playlist['owner_id'])
        user = self.get_user(owner_id)
        if user:
            user['total_songs_uploaded'] += 1

            # Check badges
            if user['total_songs_uploaded'] >= 100:
                self.add_badge(owner_id, 'music_lover')

        self.save_data()
        return True

    # ===== LIKES & INTERACTIONS =====

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
        """Get leaderboard"""
        users = []
        for user_id, user in self.data['users'].items():
            if user.get('banned'):
                continue

            if sort_by == 'likes':
                score = user.get('total_likes_received', 0)
            elif sort_by == 'plays':
                score = user.get('total_plays', 0)
            elif sort_by == 'songs':
                score = user.get('total_songs_uploaded', 0)
            else:
                score = 0

            users.append({
                'user_id': user_id,
                'name': user['first_name'],
                'username': user['username'],
                'score': score,
                'is_premium': user.get('premium', False)
            })

        users.sort(key=lambda x: x['score'], reverse=True)
        return users[:limit]

    # ===== BROWSE & DISCOVER =====

    def get_all_playlists(self, filter_private=True) -> List[Dict]:
        """Get all public playlists"""
        playlists = []
        for pl_id, playlist in self.data['playlists'].items():
            if filter_private and playlist.get('is_private'):
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
        total_playlists = len(self.data['playlists'])
        total_songs = len(self.data['songs'])
        total_users = len([u for u in self.data['users'].values() if not u.get('banned')])
        premium_users = len([u for u in self.data['users'].values() if u.get('premium')])

        # Active today
        today = datetime.now().date()
        active_today = 0  # This would need activity tracking

        return {
            'total_users': total_users,
            'active_today': active_today,
            'new_today': 0,  # Track this separately
            'total_playlists': total_playlists,
            'total_songs': total_songs,
            'total_likes': self.data['stats']['total_likes'],
            'total_plays': self.data['stats']['total_plays'],
            'premium_users': premium_users,
            'revenue': premium_users * PREMIUM_PRICE,
        }

    def get_user_rank(self, user_id: int) -> int:
        """Get user rank in leaderboard"""
        leaderboard = self.get_leaderboard(sort_by='likes', limit=999999)
        for i, user in enumerate(leaderboard):
            if user['user_id'] == str(user_id):
                return i + 1
        return 0


# Initialize database
db = Database()
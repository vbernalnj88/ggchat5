#!/usr/bin/env python3
"""
Chat Log Analyzer - Builds user profiles from chat sessions
"""

import os
import re
import json
from datetime import datetime
from collections import defaultdict

# Configuration
CHATS_DIR = "/workspace/chats"
PROCESSED_LOG_FILE = "/workspace/processed_logs.txt"
USER_PROFILES_FILE = "/workspace/user_profiles.txt"
REPORT_FILE = "/workspace/analysis_report.txt"
MY_USERNAME = "vbernalnj"

def load_processed_files():
    """Load list of already processed files"""
    if os.path.exists(PROCESSED_LOG_FILE):
        with open(PROCESSED_LOG_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_file(filename):
    """Append filename to processed log"""
    with open(PROCESSED_LOG_FILE, 'a') as f:
        f.write(filename + '\n')

def parse_chat_line(line):
    """Parse a single chat line and extract username and message"""
    # Format: [6/14/2026, 3:54:14 AM] username: message
    pattern = r'\[\d+/\d+/\d+, \d+:\d+:\d+ [AP]M\] ([^:]+): (.*)'
    match = re.match(pattern, line)
    if match:
        return match.group(1), match.group(2)
    return None, None

def extract_info_from_message(message, profile):
    """Extract relevant information from a message"""
    message_lower = message.lower()
    
    # Age patterns
    age_patterns = [
        r"i'?m?\s*(\d{1,2})\s*(years? old|yo)",
        r"(\d{1,2})\s*(years? old|yo)",
        r"age\s*(\d{1,2})",
        r"turned\s*(\d{1,2})",
    ]
    for pattern in age_patterns:
        match = re.search(pattern, message_lower)
        if match:
            age = match.group(1)
            if 10 <= int(age) <= 99:  # Reasonable age range
                profile['ages'].add(age)
    
    # Gender patterns
    gender_indicators = {
        'male': ['male', 'boy', 'guy', 'man', 'him', 'his', 'trans guy', 'trans male'],
        'female': ['female', 'girl', 'woman', 'her', 'hers', 'trans girl', 'trans female', 'lady'],
        'non-binary': ['nonbinary', 'non-binary', 'nb', 'they/them'],
        'trans': ['trans', 'mtf', 'ftm', 'transgender'],
    }
    for gender, indicators in gender_indicators.items():
        for indicator in indicators:
            if indicator in message_lower:
                profile['genders'].add(gender)
    
    # Location patterns
    location_keywords = ['live in', 'living in', 'from', 'located in', 'based in', 'i am in', "i'm in", 'im in']
    for keyword in location_keywords:
        if keyword in message_lower:
            # Try to extract location after keyword
            idx = message_lower.find(keyword)
            potential_location = message[idx + len(keyword):idx + len(keyword) + 50].strip()
            # Clean up and look for common location patterns
            loc_match = re.search(r'[\w\s]+(?:california|texas|florida|new york|ohio|illinois|pennsylvania|georgia|michigan|arizona|washington|colorado|oregon|nevada|utah|tennessee|north carolina|virginia|maryland|massachusetts|indiana|missouri|wisconsin|minnesota|alabama|louisiana|kentucky|oklahoma|connecticut|iowa|mississippi|arkansas|kansas|nebraska|west virginia|idaho|hawaii|maine|new hampshire|rhode island|montana|delaware|south dakota|north dakota|alaska|vermont|wyoming|usa|uk|canada|europe|asia|australia)', potential_location, re.IGNORECASE)
            if loc_match:
                profile['locations'].add(loc_match.group(0).strip())
            else:
                # Just take first few words as potential location
                words = potential_location.split()[:3]
                if words:
                    profile['locations'].add(' '.join(words).strip(',.'))
    
    # Likes patterns
    like_indicators = ['i love', 'i like', 'love ', 'like ', 'enjoy', 'into ', 'fan of', 'favorite', 'favourite']
    for indicator in like_indicators:
        if indicator in message_lower:
            idx = message_lower.find(indicator)
            potential_like = message[idx + len(indicator):idx + len(indicator) + 40].strip()
            # Clean up
            like = potential_like.split('\n')[0].split('.')[0].split(',')[0].strip()
            if like and len(like) > 2 and len(like) < 50:
                profile['likes'].add(like)
    
    # Dislikes patterns
    dislike_indicators = ['i hate', 'i dislike', 'hate ', 'dislike ', "don't like", "dont like", "can't stand", 'cant stand', 'not into']
    for indicator in dislike_indicators:
        if indicator in message_lower:
            idx = message_lower.find(indicator)
            potential_dislike = message[idx + len(indicator):idx + len(indicator) + 40].strip()
            dislike = potential_dislike.split('\n')[0].split('.')[0].split(',')[0].strip()
            if dislike and len(dislike) > 2 and len(dislike) < 50:
                profile['dislikes'].add(dislike)
    
    # Pic/image indicators
    pic_indicators = ['sent a pic', 'sent a photo', 'sent an image', 'here is my pic', 'here is my photo', 
                      'check my pic', 'look at my pic', 'sending pic', 'pic attached', 'photo attached',
                      'irl pic', 'real pic', 'face pic', 'body pic']
    for indicator in pic_indicators:
        if indicator in message_lower:
            profile['sent_irl_pic'] = True
    
    # Cam/webcam indicators
    cam_indicators = ['willing to cam', 'can cam', 'will cam', 'open to cam', 'down to cam', 
                      'cam yes', 'sure cam', 'okay cam', 'ok cam', 'happy to cam',
                      "won't cam", 'wont cam', 'no cam', 'not camming', 'cant cam', "can't cam"]
    for indicator in cam_indicators:
        if indicator in message_lower:
            if "won't" in indicator or "wont" in indicator or "no cam" in indicator or "not cam" in indicator or "cant" in indicator or "can't" in indicator:
                profile['cam_willing'] = False
            else:
                profile['cam_willing'] = True
    
    # Unique/interesting content (longer messages, specific details)
    if len(message) > 50 and not message.startswith('http'):
        # Check for unique statements
        unique_patterns = [
            r'(first time|never before|always wanted|bucket list)',
            r'(fetish|kink|fantasy|dream)',
            r'(job|work|school|college|university)',
            r'(hobby|interest|passion)',
        ]
        for pattern in unique_patterns:
            if re.search(pattern, message_lower):
                profile['unique_notes'].add(message[:100])
                break

def process_chat_file(filepath):
    """Process a single chat file and return user data"""
    users_data = {}
    current_user = None
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('Session:') or line.startswith('URL:') or line.startswith('Last Synced:') or line.startswith('==='):
            continue
        
        username, message = parse_chat_line(line)
        
        # Handle "Unknown" username - use previous user
        if username == 'Unknown' or username == 'Unknown username':
            if current_user is not None:
                username = current_user
                if username in users_data:
                    # Process message for the previous user
                    extract_info_from_message(message, users_data[username])
            continue
        
        if username and message:
            current_user = username
            if username not in users_data:
                users_data[username] = {
                    'ages': set(),
                    'genders': set(),
                    'locations': set(),
                    'likes': set(),
                    'dislikes': set(),
                    'sent_irl_pic': False,
                    'cam_willing': None,  # None means unknown
                    'unique_notes': set(),
                    'chatted_with_me': False,
                    'message_count': 0,
                }
            
            users_data[username]['message_count'] += 1
            
            # Check if this user chatted with MY_USERNAME
            # We need to check if MY_USERNAME appears in the same session
            extract_info_from_message(message, users_data[username])
    
    return users_data

def check_if_chatted_with_me(filepath, username):
    """Check if a user chatted in the same session as vbernalnj"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Check if both users appear in the file
    # Format is: ] username: message (note the space after bracket)
    username_pattern = f'] {username}:'
    my_pattern = f'] {MY_USERNAME}:'
    
    has_username = username_pattern in content
    has_me = my_pattern in content
    
    return has_username and has_me

def merge_profiles(existing, new):
    """Merge new profile data into existing profile"""
    for key in ['ages', 'genders', 'locations', 'likes', 'dislikes', 'unique_notes']:
        existing[key].update(new[key])
    
    if new['sent_irl_pic']:
        existing['sent_irl_pic'] = True
    
    if new['cam_willing'] is not None:
        existing['cam_willing'] = new['cam_willing']
    
    if new['chatted_with_me']:
        existing['chatted_with_me'] = True
    
    existing['message_count'] += new['message_count']

def format_profile(username, profile):
    """Format a profile as a readable note"""
    notes = []
    notes.append(f"Username: {username}")
    
    if profile['ages']:
        notes.append(f"  Age(s) mentioned: {', '.join(sorted(profile['ages']))}")
    
    if profile['genders']:
        notes.append(f"  Gender info: {', '.join(sorted(profile['genders']))}")
    
    if profile['locations']:
        notes.append(f"  Location info: {', '.join(sorted(profile['locations']))}")
    
    if profile['likes']:
        notes.append(f"  Likes: {', '.join(sorted(list(profile['likes'])[:10]))}")  # Limit to 10
    
    if profile['dislikes']:
        notes.append(f"  Dislikes: {', '.join(sorted(list(profile['dislikes'])[:10]))}")  # Limit to 10
    
    notes.append(f"  Sent IRL pic: {'Yes' if profile['sent_irl_pic'] else 'No'}")
    
    if profile['cam_willing'] is None:
        notes.append("  Willing to cam: Unknown")
    elif profile['cam_willing']:
        notes.append("  Willing to cam: Yes")
    else:
        notes.append("  Willing to cam: No")
    
    notes.append(f"  Chatted with {MY_USERNAME}: {'Yes' if profile['chatted_with_me'] else 'No'}")
    
    if profile['unique_notes']:
        notes.append(f"  Unique notes: {'; '.join(sorted(list(profile['unique_notes'])[:5]))}")  # Limit to 5
    
    notes.append(f"  Total messages: {profile['message_count']}")
    
    return '\n'.join(notes)

def main():
    print("Starting chat log analysis...")
    
    # Load already processed files
    processed_files = load_processed_files()
    print(f"Found {len(processed_files)} previously processed files")
    
    # Get all chat files
    all_files = sorted([f for f in os.listdir(CHATS_DIR) if f.endswith('.txt')])
    print(f"Found {len(all_files)} total chat files")
    
    # Filter out already processed files
    new_files = [f for f in all_files if f not in processed_files]
    print(f"Processing {len(new_files)} new files")
    
    # Load existing profiles from file if it exists and we have no new files to process
    all_profiles = {}
    users_previously_existing = set()
    
    if os.path.exists(USER_PROFILES_FILE) and len(new_files) == 0:
        # Re-read the existing profiles file to preserve data
        print("Loading existing profiles from file...")
        with open(USER_PROFILES_FILE, 'r') as f:
            content = f.read()
        
        # Parse existing profiles - extract usernames
        profile_pattern = r'^Username: (.+)$'
        for match in re.finditer(profile_pattern, content, re.MULTILINE):
            username = match.group(1).strip()
            if username:
                users_previously_existing.add(username)
                all_profiles[username] = {
                    'ages': set(),
                    'genders': set(),
                    'locations': set(),
                    'likes': set(),
                    'dislikes': set(),
                    'sent_irl_pic': False,
                    'cam_willing': None,
                    'unique_notes': set(),
                    'chatted_with_me': False,
                    'message_count': 0,
                }
        print(f"Loaded {len(all_profiles)} existing profiles")
    
    # Statistics
    stats = {
        'total_files': len(all_files),
        'new_files_processed': len(new_files),
        'already_processed': len(processed_files),
        'users_found': set(),
        'users_previously_existing': users_previously_existing,
        'sessions_with_me': 0,
    }
    
    # Process each new file
    for i, filename in enumerate(new_files):
        filepath = os.path.join(CHATS_DIR, filename)
        print(f"[{i+1}/{len(new_files)}] Processing {filename}...")
        
        # First pass: get all users and basic data
        users_data = process_chat_file(filepath)
        
        # Second pass: check who chatted with me
        for username in users_data:
            if check_if_chatted_with_me(filepath, username):
                users_data[username]['chatted_with_me'] = True
                if username == MY_USERNAME:
                    stats['sessions_with_me'] += 1
        
        # Merge into all profiles
        for username, data in users_data.items():
            stats['users_found'].add(username)
            
            if username in all_profiles:
                stats['users_previously_existing'].add(username)
                merge_profiles(all_profiles[username], data)
            else:
                all_profiles[username] = data
        
        # Mark file as processed
        save_processed_file(filename)
    
    # Write user profiles to file
    print(f"\nWriting profiles for {len(all_profiles)} users...")
    with open(USER_PROFILES_FILE, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("USER PROFILES - Chat Log Analysis\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"My Username: {MY_USERNAME}\n")
        f.write("=" * 80 + "\n\n")
        
        for username in sorted(all_profiles.keys()):
            profile = all_profiles[username]
            f.write("-" * 60 + "\n")
            f.write(format_profile(username, profile))
            f.write("\n\n")
    
    # Write report
    with open(REPORT_FILE, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("CHAT LOG ANALYSIS REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("SUMMARY STATISTICS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total chat files in directory: {stats['total_files']}\n")
        f.write(f"New files processed this run: {stats['new_files_processed']}\n")
        f.write(f"Files already processed (skipped): {stats['already_processed']}\n")
        f.write(f"Unique users found: {len(stats['users_found'])}\n")
        f.write(f"Users that existed before merge: {len(stats['users_previously_existing'])}\n")
        f.write(f"Sessions containing {MY_USERNAME}: {stats['sessions_with_me']}\n\n")
        
        f.write("USERS WHO CHATTED WITH ME\n")
        f.write("-" * 40 + "\n")
        users_with_me = [u for u, p in all_profiles.items() if p['chatted_with_me'] and u != MY_USERNAME]
        if users_with_me:
            for u in sorted(users_with_me):
                f.write(f"  - {u}\n")
        else:
            f.write("  None found\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"Total files: {stats['total_files']}")
    print(f"New files processed: {stats['new_files_processed']}")
    print(f"Already processed (skipped): {stats['already_processed']}")
    print(f"Unique users profiled: {len(all_profiles)}")
    print(f"Users who chatted with {MY_USERNAME}: {len(users_with_me)}")
    print(f"\nOutput files:")
    print(f"  - User profiles: {USER_PROFILES_FILE}")
    print(f"  - Report: {REPORT_FILE}")
    print(f"  - Processed log: {PROCESSED_LOG_FILE}")

if __name__ == "__main__":
    main()

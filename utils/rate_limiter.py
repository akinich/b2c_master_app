"""
Rate Limiter Utility
Implements rate limiting for login attempts to prevent brute force attacks

VERSION HISTORY:
1.0.0 - Login attempt rate limiting - 11/12/25
      SECURITY:
      - Track failed login attempts per email
      - Lockout after MAX_ATTEMPTS failed attempts
      - LOCKOUT_DURATION cooldown period
      - Automatic lockout expiration
"""
import time
import streamlit as st
from typing import Dict, Optional


class LoginRateLimiter:
    """
    Rate limiter for login attempts to prevent brute force attacks

    Tracks failed login attempts and locks out accounts after too many failures.
    Uses Streamlit session state for tracking (resets on browser close).

    Example:
        >>> if LoginRateLimiter.is_locked_out("user@example.com"):
        >>>     st.error("Too many login attempts...")
        >>> else:
        >>>     # Attempt login
        >>>     if login_failed:
        >>>         LoginRateLimiter.record_failed_attempt("user@example.com")
    """

    MAX_ATTEMPTS = 5  # Maximum failed attempts before lockout
    LOCKOUT_DURATION_SECONDS = 300  # 5 minutes lockout
    ATTEMPT_WINDOW_SECONDS = 300  # 5 minute window for attempt counting

    @staticmethod
    def _get_lockout_key(email: str) -> str:
        """Get session state key for tracking attempts"""
        # Use lowercase email for case-insensitive tracking
        email_lower = email.lower().strip()
        return f"login_attempts_{email_lower}"

    @staticmethod
    def is_locked_out(email: str) -> bool:
        """
        Check if account is currently locked out

        Args:
            email: User's email address

        Returns:
            True if account is locked, False otherwise
        """
        key = LoginRateLimiter._get_lockout_key(email)

        if key in st.session_state:
            lockout_data = st.session_state[key]

            # Check if there's an active lockout
            if 'locked_until' in lockout_data:
                current_time = time.time()
                if current_time < lockout_data['locked_until']:
                    return True  # Still locked
                else:
                    # Lockout expired, clear data
                    del st.session_state[key]
                    return False

        return False

    @staticmethod
    def get_lockout_remaining_seconds(email: str) -> int:
        """
        Get remaining lockout time in seconds

        Args:
            email: User's email address

        Returns:
            Remaining seconds of lockout, or 0 if not locked
        """
        key = LoginRateLimiter._get_lockout_key(email)

        if key in st.session_state:
            lockout_data = st.session_state[key]
            if 'locked_until' in lockout_data:
                remaining = int(lockout_data['locked_until'] - time.time())
                return max(0, remaining)

        return 0

    @staticmethod
    def record_failed_attempt(email: str):
        """
        Record a failed login attempt

        Increments attempt counter and triggers lockout if threshold exceeded.

        Args:
            email: User's email address
        """
        key = LoginRateLimiter._get_lockout_key(email)
        current_time = time.time()

        # Initialize or get existing attempt data
        if key not in st.session_state:
            st.session_state[key] = {
                'attempts': 0,
                'first_attempt': None,
                'locked_until': None
            }

        lockout_data = st.session_state[key]

        # Check if attempt window has expired - reset counter
        if lockout_data['first_attempt']:
            time_since_first = current_time - lockout_data['first_attempt']
            if time_since_first > LoginRateLimiter.ATTEMPT_WINDOW_SECONDS:
                # Window expired, reset attempts
                st.session_state[key] = {
                    'attempts': 1,
                    'first_attempt': current_time,
                    'locked_until': None
                }
                return
        else:
            # First attempt
            lockout_data['first_attempt'] = current_time

        # Increment attempt counter
        lockout_data['attempts'] += 1

        # Check if lockout threshold reached
        if lockout_data['attempts'] >= LoginRateLimiter.MAX_ATTEMPTS:
            lockout_data['locked_until'] = current_time + LoginRateLimiter.LOCKOUT_DURATION_SECONDS

    @staticmethod
    def record_successful_login(email: str):
        """
        Record a successful login and clear attempt history

        Args:
            email: User's email address
        """
        key = LoginRateLimiter._get_lockout_key(email)
        if key in st.session_state:
            del st.session_state[key]

    @staticmethod
    def get_remaining_attempts(email: str) -> int:
        """
        Get remaining login attempts before lockout

        Args:
            email: User's email address

        Returns:
            Number of remaining attempts (0 if locked out)
        """
        if LoginRateLimiter.is_locked_out(email):
            return 0

        key = LoginRateLimiter._get_lockout_key(email)

        if key in st.session_state:
            attempts = st.session_state[key].get('attempts', 0)
            return max(0, LoginRateLimiter.MAX_ATTEMPTS - attempts)

        return LoginRateLimiter.MAX_ATTEMPTS

    @staticmethod
    def format_lockout_message(email: str) -> str:
        """
        Format a user-friendly lockout message

        Args:
            email: User's email address

        Returns:
            Formatted message string
        """
        remaining_seconds = LoginRateLimiter.get_lockout_remaining_seconds(email)
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60

        if minutes > 0:
            return f"Too many failed login attempts. Account locked for {minutes}m {seconds}s"
        else:
            return f"Too many failed login attempts. Account locked for {seconds} seconds"

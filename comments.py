#!/usr/bin/env python3
"""
Comments/Discussion module for Reddit-style threaded comments.
Supports nested replies, voting, and user attribution.
"""

import streamlit as st
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import pytz
import database as db
import auth

logger = logging.getLogger(__name__)

# ===========================
# Comment Data Operations
# ===========================

def create_comment(resource_id: str, resource_category: str, user_id: int, 
                   content: str, parent_id: Optional[int] = None,
                   rating: Optional[int] = None) -> tuple:
    """
    Create a new comment or reply.
    rating: 1–5 for top-level reviews (ignored for replies).
    Returns (success: bool, message: str, comment_id: int or None)
    """
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return False, "Database connection failed", None

        stars = None
        if parent_id is None and rating is not None:
            try:
                stars = int(rating)
            except (TypeError, ValueError):
                stars = None
            if stars is not None and (stars < 1 or stars > 5):
                return False, "Rating must be between 1 and 5 stars", None
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO comments (resource_id, resource_category, user_id, parent_id, content, rating)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (resource_id, resource_category, user_id, parent_id, content, stars))
            
            comment_id = cur.fetchone()["id"]
            conn.commit()
            
            logger.info(f"Created comment {comment_id} for resource {resource_id}")
            return True, "Comment posted!", comment_id
            
    except Exception as e:
        logger.error(f"Error creating comment: {e}")
        return False, "Error posting comment. Please try again.", None

def get_comments_for_resource(resource_id: str, resource_category: str) -> List[Dict[str, Any]]:
    """
    Get all comments for a resource, organized for threaded display.
    Returns a list of top-level comments with nested replies.
    """
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return []
        
        with conn.cursor() as cur:
            # Get all comments with user info and vote counts
            cur.execute("""
                SELECT 
                    c.id,
                    c.resource_id,
                    c.user_id,
                    c.parent_id,
                    c.content,
                    c.rating,
                    c.created_at,
                    c.updated_at,
                    c.is_deleted,
                    u.username,
                    u.display_name,
                    COALESCE(SUM(CASE WHEN cv.vote_type = 1 THEN 1 ELSE 0 END), 0) as upvotes,
                    COALESCE(SUM(CASE WHEN cv.vote_type = -1 THEN 1 ELSE 0 END), 0) as downvotes
                FROM comments c
                JOIN users u ON c.user_id = u.id
                LEFT JOIN comment_votes cv ON c.id = cv.comment_id
                WHERE c.resource_id = %s AND c.resource_category = %s
                GROUP BY c.id, u.username, u.display_name
                ORDER BY c.created_at ASC
            """, (resource_id, resource_category))
            
            all_comments = cur.fetchall()
            
            # Convert to list of dicts
            comments_list = [dict(c) for c in all_comments]
            
            # Build threaded structure
            return build_comment_tree(comments_list)
            
    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        return []

def build_comment_tree(comments: List[Dict]) -> List[Dict]:
    """
    Build a nested tree structure from flat comment list.
    Top-level comments (parent_id=None) are returned with their replies nested.
    """
    # Create a lookup dictionary
    comment_dict = {c["id"]: {**c, "replies": []} for c in comments}
    
    # Build the tree
    root_comments = []
    for comment in comments:
        if comment["parent_id"] is None:
            root_comments.append(comment_dict[comment["id"]])
        else:
            parent = comment_dict.get(comment["parent_id"])
            if parent:
                parent["replies"].append(comment_dict[comment["id"]])
    
    # Sort root comments by rating then helpful score, then date
    root_comments.sort(
        key=lambda x: (
            -(x.get("rating") or 0),
            -(x["upvotes"] - x["downvotes"]),
            x["created_at"],
        ),
    )
    
    return root_comments

def vote_comment(comment_id: int, user_id: int, vote_type: int) -> tuple:
    """
    Vote on a comment. vote_type: 1 for upvote, -1 for downvote, 0 to remove vote.
    Returns (success: bool, message: str)
    """
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return False, "Database connection failed"
        
        with conn.cursor() as cur:
            if vote_type == 0:
                # Remove vote
                cur.execute("""
                    DELETE FROM comment_votes 
                    WHERE comment_id = %s AND user_id = %s
                """, (comment_id, user_id))
            else:
                # Upsert vote
                cur.execute("""
                    INSERT INTO comment_votes (comment_id, user_id, vote_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (comment_id, user_id) 
                    DO UPDATE SET vote_type = %s
                """, (comment_id, user_id, vote_type, vote_type))
            
            conn.commit()
            return True, "Vote recorded"
            
    except Exception as e:
        logger.error(f"Error voting on comment: {e}")
        return False, "Something went wrong. Please try again."

def get_user_vote(comment_id: int, user_id: int) -> int:
    """Get the current user's vote on a comment. Returns 1, -1, or 0."""
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return 0
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vote_type FROM comment_votes 
                WHERE comment_id = %s AND user_id = %s
            """, (comment_id, user_id))
            
            result = cur.fetchone()
            return result["vote_type"] if result else 0
            
    except Exception as e:
        logger.error(f"Error getting user vote: {e}")
        return 0

def delete_comment(comment_id: int, user_id: int) -> tuple:
    """
    Soft delete a comment (only the author can delete).
    Returns (success: bool, message: str)
    """
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return False, "Database connection failed"
        
        with conn.cursor() as cur:
            # Verify ownership
            cur.execute("""
                SELECT user_id FROM comments WHERE id = %s
            """, (comment_id,))
            
            comment = cur.fetchone()
            if not comment:
                return False, "Comment not found"
            
            if comment["user_id"] != user_id:
                return False, "You can only delete your own comments"
            
            # Soft delete
            cur.execute("""
                UPDATE comments 
                SET is_deleted = TRUE, content = '[deleted]', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (comment_id,))
            
            conn.commit()
            return True, "Comment deleted"
            
    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        return False, "Something went wrong. Please try again."

def get_comment_count(resource_id: str, resource_category: str) -> int:
    """Get the total number of comments for a resource."""
    try:
        db_instance = db.get_db_instance()
        if not db_instance:
            return 0
        
        conn = db_instance.get_connection()
        if not conn:
            return 0
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count FROM comments 
                WHERE resource_id = %s AND resource_category = %s AND NOT is_deleted
            """, (resource_id, resource_category))
            
            result = cur.fetchone()
            return result["count"] if result else 0
            
    except Exception as e:
        logger.error(f"Error getting comment count: {e}")
        # Return 0 on any error to prevent breaking the UI
        return 0

# ===========================
# UI Components
# ===========================

def format_timestamp(dt: datetime, local_tz: str = "America/Chicago") -> str:
    """
    Format a timestamp for display, converting from UTC to a local timezone.
    If the DB timestamp is naive, assume it is in UTC.
    """
    if dt is None:
        return ""
    
    try:
        tz = pytz.timezone(local_tz)
    except Exception:
        tz = timezone.utc
    
    # Normalize the DB timestamp to UTC first
    if dt.tzinfo is None:
        dt_utc = dt.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt.astimezone(timezone.utc)
    
    # Convert to local timezone for display
    dt_local = dt_utc.astimezone(tz)
    now = datetime.now(tz)
    diff = now - dt_local
    
    if diff.days > 365:
        return f"{diff.days // 365}y ago"
    elif diff.days > 30:
        return f"{diff.days // 30}mo ago"
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "just now"

def render_comment(comment: Dict, resource_id: str, resource_category: str,
                   depth: int = 0, max_depth: int = 5, local_tz: str = "America/Chicago"):
    """Render a single Yelp-style review card (with nested replies)."""
    import html as html_mod

    current_user = auth.get_current_user()
    user_id = current_user["id"] if current_user else None

    author_name = comment.get("display_name") or comment.get("username", "Anonymous")
    score = comment["upvotes"] - comment["downvotes"]
    timestamp = format_timestamp(comment["created_at"], local_tz=local_tz)
    is_deleted = comment.get("is_deleted", False)
    comment_key = f"comment_{comment['id']}_{depth}"
    initial = (author_name[:1] or "?").upper()
    margin = f"margin-left:{min(depth, 4) * 1.1}rem;" if depth else ""
    rating = comment.get("rating")
    try:
        rating_n = int(rating) if rating is not None else 0
    except (TypeError, ValueError):
        rating_n = 0
    stars_html = ""
    if rating_n >= 1:
        filled = "★" * min(rating_n, 5)
        empty = "☆" * max(0, 5 - min(rating_n, 5))
        stars_html = f'<div class="yelp-stars">{filled}{empty}</div>'

    body = "[This comment has been deleted]" if is_deleted else (comment.get("content") or "")
    safe_author = html_mod.escape(author_name if not is_deleted else "[deleted]")
    safe_body = html_mod.escape(body).replace("\n", "<br>")

    st.markdown(
        f"""
<div class="yelp-review" style="{margin}">
  <div class="yelp-review-head">
    <span class="yelp-review-avatar">{html_mod.escape(initial)}</span>
    <div class="yelp-review-meta">
      <div class="yelp-review-author">{safe_author}</div>
      {stars_html}
      <div class="yelp-review-sub">{html_mod.escape(timestamp)} · {score} helpful</div>
    </div>
  </div>
  <div class="yelp-review-body">{safe_body}</div>
</div>
<style>
.yelp-review {{
  background: #fff;
  border: 1px solid rgba(26,46,40,0.12);
  border-radius: 12px;
  padding: 0.85rem 1rem 0.55rem 1rem;
  margin: 0.55rem 0 0.35rem 0;
  box-shadow: 0 1px 3px rgba(26,46,40,0.06);
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.yelp-review-head {{ display: flex; gap: 0.65rem; align-items: center; margin-bottom: 0.45rem; }}
.yelp-review-avatar {{
  width: 2rem; height: 2rem; border-radius: 8px; flex-shrink: 0;
  background: #4EB086; color: #fff; font-weight: 700; font-size: 0.95rem;
  display: flex; align-items: center; justify-content: center;
}}
.yelp-review-author {{ font-weight: 700; color: #1a2e28; font-size: 0.95rem; }}
.yelp-stars {{ color: #4EB086; font-size: 0.95rem; letter-spacing: 0.05em; margin: 0.1rem 0; }}
.yelp-review-sub {{ font-size: 0.78rem; color: #6b8178; }}
.yelp-review-body {{ color: #2a3d36; font-size: 0.92rem; line-height: 1.45; margin-bottom: 0.35rem; }}
</style>
""",
        unsafe_allow_html=True,
    )

    if not is_deleted:
        user_vote = get_user_vote(comment["id"], user_id) if user_id else 0
        a1, a2, a3, a4, _ = st.columns([1.1, 1.1, 1.1, 1.1, 4])
        with a1:
            label = "▲ Useful" if user_vote != 1 else "▲ Useful ✓"
            if st.button(label, key=f"up_{comment_key}", use_container_width=True):
                if user_id:
                    vote_comment(comment["id"], user_id, 0 if user_vote == 1 else 1)
                    st.rerun()
                else:
                    st.toast("Please log in to vote")
        with a2:
            if st.button("▼", key=f"down_{comment_key}", use_container_width=True, help="Not useful"):
                if user_id:
                    vote_comment(comment["id"], user_id, 0 if user_vote == -1 else -1)
                    st.rerun()
                else:
                    st.toast("Please log in to vote")
        with a3:
            if depth < max_depth and st.button("Reply", key=f"reply_{comment_key}", use_container_width=True):
                if user_id:
                    st.session_state[f"replying_to_{comment['id']}"] = True
                else:
                    st.toast("Please log in to reply")
        with a4:
            if user_id and comment["user_id"] == user_id:
                if st.button("Delete", key=f"del_{comment_key}", use_container_width=True):
                    delete_comment(comment["id"], user_id)
                    st.rerun()

    if st.session_state.get(f"replying_to_{comment['id']}"):
        with st.form(key=f"reply_form_{comment_key}"):
            reply_text = st.text_area("Your reply:", key=f"reply_text_{comment_key}", height=80)
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Post Reply", use_container_width=True):
                    if reply_text.strip():
                        success, msg, _ = create_comment(
                            resource_id, resource_category, user_id,
                            reply_text.strip(), parent_id=comment["id"]
                        )
                        if success:
                            st.session_state[f"replying_to_{comment['id']}"] = False
                            st.rerun()
                        else:
                            st.error(msg)
            with col2:
                if st.form_submit_button("Cancel", use_container_width=True):
                    st.session_state[f"replying_to_{comment['id']}"] = False
                    st.rerun()

    for reply in comment.get("replies", []):
        render_comment(reply, resource_id, resource_category, depth + 1, max_depth, local_tz=local_tz)


def render_discussion_section(resource_id: str, resource_category: str, resource_name: str = ""):
    """Yelp-style reviews section  -  matches main listing cards."""
    try:
        db_ok = bool(db.get_db_instance().get_connection())
    except Exception:
        db_ok = False

    if not db_ok:
        st.info("Comments need a database connection. Listing details above still work.")
        return

    local_tz = st.session_state.get("client_timezone") or "America/Chicago"
    current_user = auth.get_current_user()
    comment_count = get_comment_count(resource_id, resource_category)

    comments_list = get_comments_for_resource(resource_id, resource_category)
    rated = [c.get("rating") for c in comments_list if c.get("rating")]
    avg_html = ""
    if rated:
        try:
            avg = sum(int(r) for r in rated) / len(rated)
            filled = "★" * int(round(avg))
            empty = "☆" * (5 - int(round(avg)))
            avg_html = f'<div class="yelp-reviews-avg">{filled}{empty} · {avg:.1f} avg</div>'
        except Exception:
            avg_html = ""

    st.markdown(
        f"""
<div class="yelp-reviews-banner">
  <div class="yelp-reviews-count">{comment_count} review{"s" if comment_count != 1 else ""}</div>
  {avg_html}
  <div class="yelp-reviews-hint">Share tips for other families  -  what helped, wait times, languages spoken.</div>
</div>
<style>
.yelp-reviews-banner {{
  background: #f7fbf9;
  border: 1px solid rgba(78,176,134,0.28);
  border-radius: 12px;
  padding: 0.85rem 1rem;
  margin: 0.35rem 0 0.75rem 0;
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.yelp-reviews-count {{ font-weight: 700; color: #1a2e28; font-size: 1.05rem; }}
.yelp-reviews-avg {{ color: #4EB086; font-size: 1rem; margin-top: 0.15rem; letter-spacing: 0.04em; }}
.yelp-reviews-hint {{ color: #4a5f56; font-size: 0.88rem; margin-top: 0.2rem; }}
</style>
""",
        unsafe_allow_html=True,
    )

    if current_user:
        with st.expander("Write a review", expanded=True):
            with st.form(key=f"new_comment_form_{resource_id}"):
                rating = st.radio(
                    "Your rating",
                    options=[5, 4, 3, 2, 1],
                    format_func=lambda n: "★" * n + "☆" * (5 - n) + f" ({n})",
                    horizontal=True,
                    index=0,
                    key=f"rating_{resource_id}",
                )
                new_comment = st.text_area(
                    "Your experience",
                    height=110,
                    placeholder="What was your experience? Any tips for others?",
                    label_visibility="collapsed",
                )
                if st.form_submit_button("Post review", use_container_width=True):
                    if new_comment.strip():
                        try:
                            success, msg, _ = create_comment(
                                resource_id,
                                resource_category,
                                current_user["id"],
                                new_comment.strip(),
                                rating=int(rating),
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(f"Could not post: {msg}")
                        except Exception as e:
                            st.error(f"Unexpected error: {e}")
                    else:
                        st.warning("Please write something before posting.")
    else:
        st.markdown(
            """
<div class="yelp-login-nudge">
  <strong>Log in to write a review.</strong> You can still read comments without an account  -  use Account in the sidebar.
</div>
<style>
.yelp-login-nudge {
  background: #eef7f2;
  border: 1.5px solid #4EB086;
  border-radius: 12px;
  padding: 0.75rem 1rem;
  color: #1a2e28;
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: 0.92rem;
  margin-bottom: 0.75rem;
}
</style>
""",
            unsafe_allow_html=True,
        )

    if comments_list:
        for comment in comments_list:
            render_comment(comment, resource_id, resource_category, local_tz=local_tz)
    else:
        st.markdown(
            """
<div class="yelp-empty-reviews">No reviews yet. Be the first to share your experience.</div>
<style>
.yelp-empty-reviews {
  color: #6b8178; font-style: italic; font-size: 0.92rem;
  padding: 0.5rem 0.15rem 1rem 0.15rem;
  font-family: 'DM Sans', system-ui, sans-serif;
}
</style>
""",
            unsafe_allow_html=True,
        )


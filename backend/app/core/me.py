from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from app.licensing.service import licensing_service
from app.auth.dependencies import get_current_user
from app.services.activation_manager import ActivationManager
from app.users import repository as user_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/plan")
async def my_plan():
    """Return the current license/plan for the (mock) user.

    No authentication is required for this endpoint (mock user).
    """
    lic = await licensing_service.get_license()
    # return pydantic model as dict for direct JSON serialization
    return {
        "plan": lic.plan,
        "valid": lic.valid,
        "expires_at": lic.expires_at,
    }


@router.get("/features")
async def my_features():
    """Return enabled features for the (mock) user based on license."""
    lic = await licensing_service.get_license()
    return {"features": lic.features}


@router.get("/activations")
async def my_activations(current_user: dict = Depends(get_current_user)):
    """
    Get user's activation credits and status.
    Returns default data if user not found (for new users).
    
    Returns:
        {
            "plan": "starter",
            "activationCredits": 1,
            "activationCreditsUsed": 0,
            "activationCreditsRemaining": 1,
            "activeBotsCount": 0,
            "maxActiveBots": 5
        }
    """
    try:
        user_id = current_user.get("user_id") or current_user.get("id")
        if not user_id:
            # Return default data for invalid user context instead of error
            logger.warning("[!] Invalid user context in /activations, returning defaults")
            return {
                "plan": "starter",
                "activationCredits": 1,
                "activationCreditsUsed": 0,
                "activationCreditsRemaining": 1,
                "activeBotsCount": 0,
                "maxActiveBots": 5,
            }
        
        # Convert to ObjectId if needed
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except:
                pass
        
        # Get user data
        user = await user_repo.find_by_id(user_id)
        if not user:
            # Return default data for new users instead of 404
            logger.warning(f"[!] User not found {user_id}, returning defaults")
            return {
                "plan": "starter",
                "activationCredits": 1,
                "activationCreditsUsed": 0,
                "activationCreditsRemaining": 1,
                "activeBotsCount": 0,
                "maxActiveBots": 5,
            }
        
        # Get plan from licensing service
        lic = await licensing_service.get_license()
        plan = lic.plan if lic else "starter"
        
        # Get activation credits
        activation_credits = user.get("activation_credits", 
                                     ActivationManager.PLAN_CREDITS.get(plan, 1))
        activation_credits_used = user.get("activation_credits_used", 0)
        activation_credits_remaining = max(0, activation_credits - activation_credits_used)
        
        # Count active bots
        # TODO: Implement actual bot counting when bot module is available
        active_bots_count = user.get("active_bots_count", 0)
        max_active_bots = 50 if plan == "enterprise" else 5
        
        logger.info(f"[✓] Retrieved activations for user {user_id}")
        
        return {
            "plan": plan,
            "activationCredits": activation_credits,
            "activationCreditsUsed": activation_credits_used,
            "activationCreditsRemaining": activation_credits_remaining,
            "activeBotsCount": active_bots_count,
            "maxActiveBots": max_active_bots,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[✗] Error getting activations: {e}")
        # Return default data instead of 500 error
        return {
            "plan": "starter",
            "activationCredits": 1,
            "activationCreditsUsed": 0,
            "activationCreditsRemaining": 1,
            "activeBotsCount": 0,
            "maxActiveBots": 5,
        }

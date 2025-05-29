import calendar
from datetime import datetime
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, extract, func, select

# from sqlalchemy import desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin
from app.core.security import get_password_hash
from app.db.models.models import Transaction, User, Wallet
from app.db.session import get_db

# from app.schemas.schemas import Transaction as TransactionSchema
from app.schemas.schemas import (
    AdminPasswordUpdateRequest,
    AdminTransactionSummary,
    BalanceSummaryResponse,
    MonthlyBalanceStat,
    MonthlyStat,
    OverallBalanceStats,
    OverallStats,
)
from app.schemas.schemas import User as UserSchema
from app.schemas.schemas import UserActiveResponseUpdate

router = APIRouter()


@router.get("/users", response_model=List[UserSchema])
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get list of all users."""
    try:
        query = select(User)
        result = await db.execute(query)
        users = result.scalars().all()
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")

    return users


@router.patch(
    "/admin/{user_id}/activate",
    response_model=UserActiveResponseUpdate,
    summary="Admin can activate/deactivate specific users",
)
async def toggle_user_active(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> UserActiveResponseUpdate:
    """Toggle user active status."""
    try:
        # Find the user
        user_id_str = str(user_id)
        query = select(User).where(User.id == user_id_str)
        # query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")

        # Toggle the active status
        old_status = user.is_active
        new_status = not old_status
        user.is_active = bool(new_status)  # type: ignore

        # Commit the changes
        await db.commit()
        await db.refresh(user)

        return UserActiveResponseUpdate(
            success=True,
            message=f"User {'activated' if new_status else 'deactivated'} successfully",
            is_active=new_status,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error in toggle_user_active: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update user status: {str(e)}"
        )


@router.put("/admin/{user_id}/password", summary="Admin updates user's password")
async def update_user_password(
    user_id: UUID,
    payload: AdminPasswordUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    """Admin updates a specific user's password."""
    try:
        result = await db.execute(select(User).where(User.id == str(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.hashed_password = get_password_hash(payload.new_password)  # type: ignore
        await db.commit()
        return {"message": f"Password updated successfully for user {user_id}"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update password: {str(e)}")


@router.get("/transactions/summary", response_model=AdminTransactionSummary)
async def get_admin_transaction_summary(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> AdminTransactionSummary:
    now = datetime.utcnow()
    current_month = now.month
    current_year = now.year

    monthly_stats: List[MonthlyStat] = []
    total_volume = 0.0
    total_transactions = 0
    previous_valid_avg = None  # Only compare to previous months with real data

    for month_num in range(1, current_month + 1):
        month_name = datetime(2000, month_num, 1).strftime("%b")

        result = await db.execute(
            select(func.count(Transaction.id), func.sum(Transaction.amount), func.avg(Transaction.amount)).where(
                extract("month", Transaction.created_at) == month_num,
                extract("year", Transaction.created_at) == current_year,
            )
        )

        tx_count, volume, avg = result.one()
        tx_count = tx_count or 0
        volume = volume or 0.0
        avg = avg or 0.0

        # Calculate trend and changePercentage
        if previous_valid_avg is None or previous_valid_avg == 0:
            trend = "up" if avg > 0 else "stable"
            change = 100.0 if avg > 0 else 0.0
        else:
            change = (avg - previous_valid_avg) / previous_valid_avg * 100
            trend = "stable" if abs(change) < 0.1 else ("up" if change > 0 else "down")

        # Update previous comparison point if current avg is valid
        if avg > 0:
            previous_valid_avg = avg

        monthly_stats.append(
            MonthlyStat(
                month=month_name,
                monthNumber=month_num,
                averageAmount=round(avg, 2),
                totalTransactions=tx_count,
                totalVolume=round(volume, 2),
                trend=trend,
                changePercentage=round(change, 2),
            )
        )

        total_volume += volume
        total_transactions += tx_count

    # Overall calculations
    overall_avg = total_volume / total_transactions if total_transactions else 0.0

    # Month-over-month growth (last 2 valid months)
    valid_months = [m for m in monthly_stats if m.averageAmount > 0]
    if len(valid_months) >= 2:
        prev = valid_months[-2].averageAmount
        curr = valid_months[-1].averageAmount
        mom_growth = ((curr - prev) / prev * 100) if prev > 0 else 0.0
    else:
        mom_growth = 0.0

    return AdminTransactionSummary(
        overallStats=OverallStats(
            totalTransactions=total_transactions,
            totalVolume=round(total_volume, 2),
            overallAverage=round(overall_avg, 2),
            monthOverMonthGrowth=round(mom_growth, 2),
        ),
        monthlyStats=monthly_stats,
        lastUpdated=now,
    )


@router.get("/balances/summary", response_model=BalanceSummaryResponse)
async def get_balance_summary(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> BalanceSummaryResponse:
    now = datetime.utcnow()
    current_month = now.month

    monthly_stats: list[MonthlyBalanceStat] = []
    prev_avg: float | None = None
    prev_total: float | None = None
    prev_count: int | None = None
    total_new_users: int = 0

    for month_num in range(1, current_month + 1):
        # Start of the month
        start = datetime(now.year, month_num, 1)
        # End of the month (inclusive last second)
        _, last_day = calendar.monthrange(now.year, month_num)
        end = datetime(now.year, month_num, last_day, 23, 59, 59)
        month_name = start.strftime("%b")

        # Count new users
        new_users = await db.scalar(
            select(func.count(User.id)).where(and_(User.created_at >= start, User.created_at <= end))
        )

        # Wallet stats
        result = await db.execute(
            select(func.count(Wallet.id), func.sum(Wallet.balance), func.avg(Wallet.balance)).where(
                and_(Wallet.created_at >= start, Wallet.created_at <= end)
            )
        )
        count, total, avg = result.one()
        count = count or 0
        total = float(total or 0)
        avg = float(avg or 0)

        # Trend logic
        def calc_change(curr: float | int, prev: float | int | None) -> tuple[str, float]:
            if prev is None or prev == 0:
                return ("up" if curr > 0 else "stable", 100.0 if curr > 0 else 0.0)
            change = ((curr - prev) / prev) * 100
            trend = "up" if change > 0 else "down" if change < 0 else "stable"
            return trend, round(change, 2)

        avg_trend, avg_change = calc_change(avg, prev_avg)
        total_trend, total_change = calc_change(total, prev_total)
        user_trend, user_change = calc_change(count, prev_count)

        monthly_stats.append(
            MonthlyBalanceStat(
                month=month_name,
                monthNumber=month_num,
                averageBalance=round(avg, 2),
                totalBalance=round(total, 2),
                userCount=count,
                avgTrend=avg_trend,
                totalTrend=total_trend,
                userTrend=user_trend,
                avgChangePercentage=avg_change,
                totalChangePercentage=total_change,
                userChangePercentage=user_change,
                newUsers=new_users or 0,
            )
        )

        total_new_users += new_users or 0
        prev_avg, prev_total, prev_count = avg, total, count

    latest = monthly_stats[-1] if monthly_stats else None
    second_latest = monthly_stats[-2] if len(monthly_stats) >= 2 else None

    def extract_growth(metric: str) -> float:
        if not latest or not second_latest:
            return 0.0
        prev = float(getattr(second_latest, metric))
        curr = float(getattr(latest, metric))
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return round(((curr - prev) / prev) * 100, 2)

    return BalanceSummaryResponse(
        monthlyStats=monthly_stats,
        overallStats=OverallBalanceStats(
            totalUsers=latest.userCount if latest else 0,
            currentTotalBalance=latest.totalBalance if latest else 0.0,
            currentAverageBalance=latest.averageBalance if latest else 0.0,
            avgMonthOverMonthGrowth=extract_growth("averageBalance"),
            totalMonthOverMonthGrowth=extract_growth("totalBalance"),
            userMonthOverMonthGrowth=extract_growth("userCount"),
            totalNewUsersThisYear=total_new_users,
        ),
        lastUpdated=now,
    )

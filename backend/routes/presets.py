"""Filter-preset routes — saved, reusable news-filter settings, per user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from auth import get_current_user
from database import get_session
from models.db import FilterPreset, User
from models.schemas import NewsFilters, PresetCreate, PresetOut

router = APIRouter(prefix="/presets", tags=["presets"])


def _to_out(preset: FilterPreset) -> PresetOut:
    return PresetOut(
        id=preset.id,
        name=preset.name,
        filters=NewsFilters(**preset.filters),
        created_at=preset.created_at,
    )


@router.get("", response_model=list[PresetOut])
def list_presets(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> list[PresetOut]:
    rows = session.exec(
        select(FilterPreset)
        .where(FilterPreset.user_id == user.id)
        .order_by(FilterPreset.created_at.desc())
    ).all()
    return [_to_out(p) for p in rows]


@router.post("", response_model=PresetOut, status_code=201)
def create_preset(
    req: PresetCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PresetOut:
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required.")

    # One name per user — overwrite if it already exists.
    existing = session.exec(
        select(FilterPreset).where(
            FilterPreset.user_id == user.id, FilterPreset.name == name
        )
    ).first()
    if existing:
        existing.filters = req.filters.model_dump()
        preset = existing
    else:
        preset = FilterPreset(
            user_id=user.id, name=name, filters=req.filters.model_dump()
        )
        session.add(preset)

    session.commit()
    session.refresh(preset)
    return _to_out(preset)


@router.delete("/{preset_id}", status_code=204)
def delete_preset(
    preset_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    preset = session.get(FilterPreset, preset_id)
    if preset and preset.user_id == user.id:
        session.delete(preset)
        session.commit()

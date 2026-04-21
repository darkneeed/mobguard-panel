# Admin/Data Architecture Notes

## Service boundaries
- `api/services/data_admin.py` is a stable facade used by routers and tests.
- Domain logic should live in dedicated modules:
  - `data_admin_user_cards`
  - `data_admin_overrides_cache`
  - `data_admin_learning`
  - `data_admin_exports`

## Store boundaries
- `PlatformStore` is a facade for API code.
- Repository-style internals should absorb domain logic instead of growing `store.py`.
- Current extracted internal domains:
  - module admin/runtime persistence
  - review cases, analysis events, and learning promotion

## Rule of thumb
- New admin/data logic should be added to a domain module or repository first.
- Do not re-expand `DataPage.tsx`, `data_admin.py`, or `PlatformStore` with unrelated domain behavior.

---
name: rulings-kan437
description: Standing product/technical/experience rulings from the KAN-437 Alpha listings/favourites/price/skill round (2026-10-08), with source
metadata:
  type: project
---
> **Note 2026-11-10 (Thebes System).** The migration line below is superseded: teams never run `DROP` or `apply_migration`, and Memphis applies migrations (`agent/DECISIONS.md` TH-054). The integration target is `staging`, not Alpha (D-052).

Source: pm_ledger (`python3 -m agent.execution.pm_ledger show`), logged 2026-10-08, ticket KAN-437 (Alpha integration). Re-read the ledger each run; this is a snapshot.

- Listings phase two (CEO): match the design even where code backing is missing; build what exists first; unprepared items designed together later.
- Venues (CEO): rating = venue_rating_aggregate; Top rated >= 4.5; Open now computed; Instant booking deferred; no "All sports" tab; keep Indoor/Outdoor tag; cover placeholder until photos.
- Card heart = FAVOURITE (count shown), not post-like. Share = OS share sheet, no count yet (CEO).
- One favourites table for venues, games, meetups: public.favorites + toggle_favorite (CEO + CTO v2). CTO: nullable game_id/meetup_id/venue_id FKs + exactly-one CHECK; toggle_favorite SECURITY INVOKER using auth.uid(); counts computed on read; old objects renamed *_legacy and revoked, NO DROP.
- Games and meetups default sort = Starting soonest (within the hour, today, tomorrow, next week) (CEO).
- Skill: three levels everywhere. Beginner 1-3, Intermediate 4-6, Advanced 7-10. No Pro (CEO).
- Game price: required field in create/edit (games.price_aed). NULL shows "Ask" (never Free); 0 shows "Free". Venue-rental split logic (host pays / split / organiser split) DEFERRED (CEO).
- Card note "N following" = one-way follows active in the game; mutual friends later; never the word "friends" (CEO).
- Meetups: Popular tag at >=50% capacity or >=20 going; requirement and Women-only tags deferred; no venue => host must choose Indoor/Outdoor (CEO).
- Favourite toggle: toast names the type (added/removed), action area updates at once; rollback + error toast on failure (CEO).
- Block guard: hosts who blocked the viewer are hidden from nearby games; legacy *_legacy_v* functions revoked from PUBLIC/anon/authenticated; rpc_update_game no anon (CEO).
- Teams on live Supabase: no DROP, no apply_migration, no test writes (prove read-only + mocked tests). NOTE: D-042 draft section 6 supersedes this once built (class A/B migrations delegated to Operations).

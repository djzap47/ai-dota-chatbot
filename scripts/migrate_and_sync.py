import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import get_engine, SessionLocal
from app.services.stratz import sync_hero_stats
from app.models import Hero, HeroStat

def run_migration():
    print("Connecting to database...")
    with get_engine().begin() as conn:
        # 1. Add roles column to heroes if not exists
        print("Checking/adding 'roles' column in 'heroes' table...")
        conn.execute(text("ALTER TABLE heroes ADD COLUMN IF NOT EXISTS roles TEXT;"))

        # 2. Deduplicate hero_stats by keeping only the row with the max id per hero_id
        print("Deduplicating existing hero_stats rows...")
        conn.execute(text("""
            DELETE FROM hero_stats
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM hero_stats
                GROUP BY hero_id
            );
        """))

        # 3. Add UNIQUE constraint to hero_id if not exists
        print("Adding UNIQUE constraint on hero_stats(hero_id)...")
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'unique_hero_id'
                ) THEN
                    ALTER TABLE hero_stats ADD CONSTRAINT unique_hero_id UNIQUE (hero_id);
                END IF;
            END $$;
        """))

    print("Database schema migration completed successfully!")
    
    print("\nRunning STRATZ scraper to populate fresh roles and latest single-day stats...")
    db = SessionLocal()
    try:
        updated = sync_hero_stats(db)
        print(f"Successfully synced {updated} heroes with official roles and latest stats!")
        
        # Verify
        pudge = db.query(HeroStat).filter(HeroStat.hero_name == 'Pudge').first()
        if pudge:
            print(f"\nVerification -> Pudge: {pudge.win_rate}% winrate across {pudge.match_count} matches.")
            
        clinkz_hero = db.query(Hero).filter(Hero.name == 'Clinkz').first()
        clinkz_stat = db.query(HeroStat).filter(HeroStat.hero_name == 'Clinkz').first()
        if clinkz_hero:
            print(f"Verification -> Clinkz roles in DB: {clinkz_hero.roles}")
        if clinkz_stat:
            print(f"Verification -> Clinkz stats: {clinkz_stat.win_rate}% winrate across {clinkz_stat.match_count} matches.")

        total_heroes = db.query(Hero).count()
        total_stats = db.query(HeroStat).count()
        print(f"\nTotal heroes in DB: {total_heroes}")
        print(f"Total stats in DB (should match heroes 1-to-1): {total_stats}")

    finally:
        db.close()

if __name__ == "__main__":
    run_migration()

import time
import os
import schedule
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from stats.services.stratz import fetch_hero_stats
from stats.models import Hero, HeroStat
from django.utils import timezone

load_dotenv()

class Command(BaseCommand):
    help = 'Runs a daily scraper to fetch STRATZ data and update Supabase'

    def handle(self, *args, **options):
        self.stdout.write("Starting scraper scheduler. Press Ctrl+C to stop.")
        self.job()
        schedule.every().day.at("00:00").do(self.job)

        while True:
            schedule.run_pending()
            time.sleep(60)

    def job(self):
        self.stdout.write(f"[{timezone.now()}] Fetching data from STRATZ...")
        try:
            results = fetch_hero_stats()
            self.stdout.write(f"Fetched stats for {len(results)} heroes.")
            
            for item in results:
                hero, _ = Hero.objects.update_or_create(
                    id=item['hero_id'],
                    defaults={'name': item['hero_name']}
                )
                
                HeroStat.objects.create(
                    hero=hero,
                    hero_name=item['hero_name'],
                    match_count=item['match_count'],
                    win_count=item['win_count'],
                    win_rate=item['win_rate'],
                )
                
            self.stdout.write(self.style.SUCCESS(f"[{timezone.now()}] Successfully updated database."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching data: {e}"))

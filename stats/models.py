from django.db import models

class Hero(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField()

    class Meta:
        db_table = 'heroes'
        managed = False

    def __str__(self):
        return self.name

class HeroStat(models.Model):
    id = models.AutoField(primary_key=True)
    hero = models.ForeignKey(Hero, on_delete=models.CASCADE, db_column='hero_id')
    hero_name = models.TextField(null=True, blank=True)
    win_rate = models.FloatField(null=True, blank=True)
    match_count = models.IntegerField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    win_count = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'hero_stats'
        managed = False

    def __str__(self):
        return f"{self.hero_name} - {self.win_rate}% ({self.recorded_at})"

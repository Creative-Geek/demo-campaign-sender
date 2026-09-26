# seed.py
"""Seed the database with a test campaign and 200 recipients."""

from app.database import init_db, SessionLocal
from app.models import Campaign, Recipient, SendLog


def seed():
    init_db()
    db = SessionLocal()

    db.query(SendLog).delete() # wipe previous send history
    db.query(Recipient).delete() # wipe old recipient list
    db.query(Campaign).delete() # wipe old campaigns
    db.commit()

    campaign = Campaign(
        name="Q3 Product Launch Announcement",
        subject="Exciting News: Our New Platform is Live!",
        body="Hi there! We're thrilled to announce the launch of our new platform...",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    campaign_id = campaign.id
    campaign_name = campaign.name

    for i in range(200): # generate 200 dummy recipients
        db.add(Recipient(
            campaign_id=campaign_id,
            email=f"employee{i:03d}@bigcorp.example.com",
        ))
    db.commit()
    db.close()
    print(f"Seeded campaign '{campaign_name}' (ID: {campaign_id}) with 200 recipients.")


if __name__ == "__main__":
    seed()

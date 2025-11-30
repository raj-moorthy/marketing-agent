import os
import datetime
import json
import requests
import cloudinary
import cloudinary.uploader
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import config
import qrcode
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROCESSED_FOLDER'] = 'static/processed'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///realtime_agent.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# -----------------------------------------------------------
# 🚨 PASTE YOUR NGROK URL HERE
# -----------------------------------------------------------
BASE_URL = "https://e4e48b54bce5.ngrok-free.app" 

COMPANY_ADDRESS = "KCE@Coimbatore | Call: +91 9385789540"
LOGO_PATH = "static/logo.png"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
genai.configure(api_key=config.GEMINI_API_KEY)
cloudinary.config(cloud_name=config.CLOUDINARY_CLOUD_NAME, api_key=config.CLOUDINARY_API_KEY, api_secret=config.CLOUDINARY_API_SECRET)

# --- DATABASE ---
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platforms = db.Column(db.String(100))
    image_url = db.Column(db.String(300)) 
    caption = db.Column(db.Text)
    status = db.Column(db.String(50)) 
    scheduled_time = db.Column(db.String(50), nullable=True)
    impressions = db.Column(db.Integer, default=0)
    engagement = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

# --- EMAIL ENGINE ---
def send_lead_email(name, phone, date, msg):
    print(f"📧 Sending email to {config.EMAIL_RECEIVER}...")
    try:
        email_msg = MIMEMultipart()
        email_msg['From'] = config.EMAIL_SENDER
        email_msg['To'] = config.EMAIL_RECEIVER
        email_msg['Subject'] = f"📅 New Booking: {date} - {name}"
        body = f"<h2>New Lead</h2><p>Name: {name}</p><p>Phone: {phone}</p><p>Date: {date}</p><p>Note: {msg}</p>"
        email_msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.send_message(email_msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ EMAIL ERROR: {str(e)}")
        return False

# --- IMAGE ENGINE (PREMIUM STYLE) ---
class ImageHandler:
    def add_branding(self, img):
        base_width = 1080
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img = img.resize((base_width, h_size), Image.Resampling.LANCZOS).convert("RGBA")
        
        # Transparent Overlay Layer
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        try: 
            font = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except: 
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # 1. LOGO (Top Right - 8% Width)
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH).convert("RGBA")
            target_w = int(base_width * 0.08)
            w_percent = (target_w / float(logo.size[0]))
            target_h = int((float(logo.size[1]) * float(w_percent)))
            logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
            overlay.paste(logo, (base_width - target_w - 30, 30), logo)

        # 2. QR CODE (Top Left - Compact with Backing)
        booking_link = f"{BASE_URL}/booking"
        qr = qrcode.QRCode(box_size=10, border=0)
        qr.add_data(booking_link)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        
        qr_size = 90
        qr_img = qr_img.resize((qr_size, qr_size))
        
        # Draw nice backing card for QR
        card_padding = 10
        card_w = qr_size + (card_padding * 2)
        card_h = qr_size + (card_padding * 2) + 20
        
        # Semi-transparent white card
        draw.rectangle([20, 20, 20 + card_w, 20 + card_h], fill=(255, 255, 255, 220))
        
        # Paste QR
        overlay.paste(qr_img, (20 + card_padding, 20 + card_padding))
        
        # Text
        text_bbox = draw.textbbox((0,0), "SCAN TO BOOK", font=font_small)
        text_w = text_bbox[2] - text_bbox[0]
        text_x = 20 + (card_w - text_w) / 2
        draw.text((text_x, 20 + qr_size + card_padding + 2), "SCAN TO BOOK", fill="black", font=font_small)

        # 3. DETAILS (Floating Pill Style)
        # Calculate text size first
        text_bbox = draw.textbbox((0, 0), COMPANY_ADDRESS, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        
        pill_w = text_w + 60
        pill_h = text_h + 30
        pill_x = (base_width - pill_w) / 2
        pill_y = h_size - pill_h - 40 # 40px from bottom edge
        
        # Draw Pill (Black with 80% Opacity)
        draw.rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], fill=(0, 0, 0, 200))
        
        # Draw Text Centered in Pill
        draw.text((pill_x + 30, pill_y + 15), COMPANY_ADDRESS, fill="white", font=font)
        
        return Image.alpha_composite(img, overlay)

    def process_request(self, file_storage, text_prompt):
        if file_storage:
            raw_path = os.path.join(app.config['UPLOAD_FOLDER'], file_storage.filename)
            file_storage.save(raw_path)
            img = Image.open(raw_path).convert("RGBA")
        else:
            enhanced_prompt = f"Professional corporate photography poster, {text_prompt}, high resolution, realistic, cinematic lighting"
            api_url = f"https://image.pollinations.ai/prompt/{enhanced_prompt}"
            res = requests.get(api_url)
            img = Image.open(BytesIO(res.content)).convert("RGBA")
        
        img = self.add_branding(img)
        filename = f"gen_{int(datetime.datetime.now().timestamp())}.png"
        save_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
        img.save(save_path, format="PNG")
        res = cloudinary.uploader.upload(save_path)
        return save_path, res['secure_url']

# --- AI AGENT (UNCHANGED) ---
class ContentAgent:
    def generate_captions(self, local_path, topic):
        try:
            img = Image.open(local_path)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            Topic: {topic if topic else "Professional Photography"}
            Context: High-End Photography Studio Marketing.
            
            Analyze the image visually (lighting, emotion, composition) and generate 3 distinct social media posts in JSON format.
            Keys must be: "linkedin", "facebook", "instagram".
            
            STRICT RULES FOR CONTENT:
            1. **LINKEDIN (Deep Dive):** Min 200 words. Discuss technical art (lighting, ISO) and storytelling. Professional Tone.
            2. **FACEBOOK (Community):** Min 100 words. Engaging, family-friendly, questions.
            3. **INSTAGRAM (Visuals):** Punchy hook + 30 Hashtags.
            
            MANDATORY ENDING: "Scan the QR code on the image to book your session today!"
            """
            
            response = model.generate_content([prompt, img])
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"AI Error: {e}")
            return {
                "linkedin": "At our studio, we believe photography is about freezing time. This image represents our technical capability. Scan the QR code to secure your date.",
                "facebook": "Capturing memories is our passion! ❤️ Look at the emotion in this shot. Scan the code to book!",
                "instagram": "Chasing light and capturing souls. ✨ \nScan to Book! 📸 \n\n#Photography #Portrait #Studio #Canon #Art #BookNow"
            }

# --- REAL BROADCASTER ---
class SocialBroadcaster:
    def post_to_apis(self, platforms, captions, image_url):
        results = {}
        # LinkedIn
        if 'linkedin' in platforms:
            try:
                author = config.LINKEDIN_PERSON_URN.replace("urn:li:member:", "urn:li:person:")
                url = "https://api.linkedin.com/v2/ugcPosts"
                headers = {"Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "author": author,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": captions.get('linkedin', '')},
                            "shareMediaCategory": "ARTICLE",
                            "media": [{"status": "READY", "originalUrl": image_url, "title": {"text": "Post"}}]
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
                }
                r = requests.post(url, headers=headers, json=payload)
                results['linkedin'] = "✅ Posted" if r.status_code == 201 else f"❌ Failed: {r.text}"
            except Exception as e: results['linkedin'] = str(e)

        # Facebook
        if 'facebook' in platforms:
            try:
                fb_url = f"https://graph.facebook.com/{config.FB_PAGE_ID}/photos"
                payload = {"url": image_url, "message": captions.get('facebook', ''), "access_token": config.FB_PAGE_ACCESS_TOKEN}
                r = requests.post(fb_url, data=payload)
                if 'id' in r.json(): results['facebook'] = "✅ Posted"
                else: results['facebook'] = f"❌ Failed: {r.json()}"
            except Exception as e: results['facebook'] = str(e)

        # Instagram
        if 'instagram' in platforms:
            try:
                create_url = f"https://graph.facebook.com/v18.0/{config.IG_USER_ID}/media"
                payload = {"image_url": image_url, "caption": captions.get('instagram', ''), "access_token": config.FB_PAGE_ACCESS_TOKEN}
                r = requests.post(create_url, data=payload)
                data = r.json()
                if 'id' in data:
                    pub_url = f"https://graph.facebook.com/v18.0/{config.IG_USER_ID}/media_publish"
                    pub_payload = {"creation_id": data['id'], "access_token": config.FB_PAGE_ACCESS_TOKEN}
                    r2 = requests.post(pub_url, data=pub_payload)
                    if 'id' in r2.json(): results['instagram'] = "✅ Posted"
                    else: results['instagram'] = f"❌ Pub Fail: {r2.json()}"
                else: results['instagram'] = f"❌ Up Fail: {data}"
            except Exception as e: results['instagram'] = str(e)

        return results

img_handler = ImageHandler()
agent = ContentAgent()
broadcaster = SocialBroadcaster()

# --- ROUTES ---
@app.route('/')
def home(): return render_template('home.html')

@app.route('/booking')
def booking_page(): return render_template('booking.html')

@app.route('/dashboard')
def dashboard():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    
    total_impressions = db.session.query(func.sum(Post.impressions)).scalar() or 0
    total_clicks = db.session.query(func.sum(Post.clicks)).scalar() or 0
    active_campaigns = Post.query.filter(Post.status.contains('Scheduled')).count()
    eng_rate = 5.2
    
    recent = posts[:7]
    trend_labels = [p.timestamp.strftime('%d/%m') for p in recent][::-1]
    trend_data = [p.impressions for p in recent][::-1]
    li_pct = Post.query.filter(Post.platforms.contains('linkedin')).count()
    fb_pct = Post.query.filter(Post.platforms.contains('facebook')).count()
    ig_pct = Post.query.filter(Post.platforms.contains('instagram')).count()

    stats = {
        "total_impressions": f"{total_impressions:,}", "engagement_rate": f"{eng_rate}%",
        "link_clicks": f"{total_clicks:,}", "active_campaigns": active_campaigns,
        "trend_labels": trend_labels, "trend_data": trend_data,
        "li_pct": li_pct, "fb_pct": fb_pct, "ig_pct": ig_pct
    }
    return render_template('dashboard.html', posts=posts, stats=stats)

@app.route('/api/submit_booking', methods=['POST'])
def submit_booking():
    success = send_lead_email(request.form.get('name'), request.form.get('phone'), request.form.get('date'), request.form.get('message'))
    if success: return render_template('booking.html', success=True)
    return "Error sending email.", 500

@app.route('/api/chat_generate', methods=['POST'])
def chat_generate():
    prompt = request.form.get('prompt')
    file = request.files.get('file')
    if not file and not prompt: return jsonify({"error": "Provide file or text"}), 400
    local_path, public_url = img_handler.process_request(file, prompt)
    captions = agent.generate_captions(local_path, prompt)
    return jsonify({"image_url": public_url, "captions": captions})

@app.route('/api/confirm_post', methods=['POST'])
def confirm_post():
    data = request.json
    action = data.get('action')
    results = {}
    
    if action == 'instant':
        results = broadcaster.post_to_apis(data.get('platforms'), data.get('captions'), data.get('image_url'))
        failures = [k for k, v in results.items() if "Failed" in v]
        status = "Published" if not failures else "Failed"
    else:
        status = f"Scheduled: {data.get('time')}"
        results = {"system": "Queued"}

    new_post = Post(
        platforms=",".join(data.get('platforms')), 
        image_url=data.get('image_url'), 
        caption=data.get('captions')['linkedin'], 
        status=status, 
        scheduled_time=data.get('time'),
        impressions=random.randint(500, 2000), 
        engagement=random.randint(50, 150),
        clicks=random.randint(10, 40)
    )
    db.session.add(new_post)
    db.session.commit()
    return jsonify({"status": "success", "details": results})

if __name__ == '__main__':
    # host='0.0.0.0' is REQUIRED for Docker
    app.run(host='0.0.0.0', debug=True, port=5000)
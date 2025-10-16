# 🎓 LearnWorlds Integration Guide

## Overview
This guide explains how to integrate the Coherence AI Tutor with LearnWorlds, including both the student chat interface and the comprehensive admin dashboard.

## 📋 Integration Files

### 1. Student Chat Integration
**File:** `learnworlds-integration.html`
- **Purpose:** Provides AI tutor chat for students
- **Features:** Floating chat button, slide-up panel, JWT authentication
- **Access:** Available to all logged-in students

### 2. Admin Dashboard Integration  
**File:** `admin-learnworlds-integration.html`
- **Purpose:** Full admin dashboard with comprehensive analytics
- **Features:** Complete statistics, student management, flagged content review
- **Access:** Restricted to admin emails only

## 🚀 Deployment Steps

### Step 1: Deploy Your Backend
1. Ensure your Flask app is deployed to Vercel at: `https://coherence-tutor.vercel.app`
2. Verify all environment variables are set:
   - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - `JWT_SECRET`, `FLASK_SECRET_KEY`
   - `ADMIN_EMAILS` (comma-separated list)

### Step 2: LearnWorlds Integration

#### For Student Chat:
1. In LearnWorlds, go to **Site Builder** → **Custom Code**
2. Create a new **Custom Code** element
3. Paste the contents of `learnworlds-integration.html`
4. Set the placement to **Before closing body tag**
5. Save and publish

#### For Admin Dashboard:
1. Create a new **Page** in LearnWorlds
2. Add a **Custom Code** element
3. Paste the contents of `admin-learnworlds-integration.html`
4. Set page visibility to **Private** (admin only)
5. Save and publish

## 🔧 Configuration

### Backend URL
Both integration files are configured to use:
```javascript
const BACKEND = "https://coherence-tutor.vercel.app";
```

### Admin Email List
The admin dashboard restricts access to these emails:
- `andrew@coherence.org`
- `mina@coherenceeducation.org`
- `support@coherenceeducation.org`
- `evan.senour@gmail.com`
- `gavinli.automation@gmail.com`

## 📊 Admin Dashboard Features

### Comprehensive Analytics
1. **Engagement Metrics**
   - Total chats and sessions
   - Average messages per session
   - Session duration tracking
   - Active student counts

2. **Academic Focus**
   - Top 5 subjects being asked about
   - Question counts per subject
   - Unique student engagement per topic

3. **Curiosity & Creativity**
   - Open-ended vs factual question analysis
   - Creative thinking indicators
   - Question type distribution

4. **Progress Indicators**
   - Student growth tracking
   - Question depth analysis
   - Development metrics over time

5. **Wellbeing & Tone**
   - Sentiment analysis (positive/neutral/negative)
   - Emotional tone tracking
   - Daily sentiment trends

6. **Topic Analysis**
   - Most popular topics
   - Student engagement per topic
   - Content categorization

### Student Management
- View all students and their activity
- Access individual conversation histories
- Monitor engagement patterns
- Track learning progress

### Content Moderation
- Review flagged content
- Monitor safety concerns
- Track content violations
- Manage student wellbeing

## 🔐 Security Features

### Authentication
- JWT token-based authentication
- LearnWorlds user integration
- Admin role verification
- Token caching for performance

### Access Control
- Admin-only dashboard access
- Email-based permission system
- Secure token generation
- Session management

## 🎨 User Experience

### Student Interface
- **Floating Chat Button:** Always accessible graduation cap icon
- **Slide-up Panel:** Smooth animations and responsive design
- **Mobile Optimized:** Works on all device sizes
- **Brand Consistent:** Matches Coherence Education colors

### Admin Interface
- **Full Dashboard:** Comprehensive analytics and management
- **Real-time Data:** Live statistics and updates
- **Visual Analytics:** Charts, progress bars, and metrics
- **Responsive Design:** Works on desktop and mobile

## 🚨 Troubleshooting

### Common Issues

1. **Admin Dashboard Not Loading**
   - Check if user email is in admin list
   - Verify JWT token generation
   - Check browser console for errors

2. **Chat Not Appearing**
   - Ensure user is logged into LearnWorlds
   - Check if Liquid variables are rendering
   - Verify backend URL is correct

3. **Authentication Errors**
   - Check JWT secret configuration
   - Verify admin email list
   - Ensure database connection

### Debug Mode
Add this to your integration files for debugging:
```javascript
const DEBUG = true; // Set to true for console logging
```

## 📈 Analytics Data

### Data Collection
The system automatically collects:
- Student messages and responses
- Session durations and patterns
- Topic classifications
- Sentiment analysis
- Progress indicators

### Data Privacy
- All data is stored securely in your database
- No external analytics services used
- GDPR compliant data handling
- Admin-only access to sensitive data

## 🔄 Updates and Maintenance

### Regular Tasks
1. **Monitor Flagged Content:** Review safety concerns daily
2. **Check Analytics:** Review engagement and progress weekly
3. **Update Keywords:** Refine topic classification as needed
4. **Backup Data:** Ensure database backups are current

### Scaling Considerations
- Database performance monitoring
- Rate limiting adjustments
- Content safety rule updates
- Admin user management

## 📞 Support

For technical support or questions:
- **Email:** support@coherenceeducation.org
- **Admin Access:** Contact system administrators
- **Documentation:** Refer to this guide and code comments

---

## ✅ Integration Checklist

- [ ] Backend deployed to Vercel
- [ ] Environment variables configured
- [ ] Student chat integration added to LearnWorlds
- [ ] Admin dashboard page created
- [ ] Admin emails verified
- [ ] Test authentication flow
- [ ] Verify analytics data collection
- [ ] Test on mobile devices
- [ ] Review security settings
- [ ] Train admin users on dashboard features

**Integration Complete! 🎉**

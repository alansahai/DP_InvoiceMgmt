# 🛡️ AI-Powered Invoice Auditor - User Guide

## Table of Contents
1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [User Roles & Permissions](#user-roles--permissions)
4. [Core Features](#core-features)
5. [Workflow Guide](#workflow-guide)
6. [Dashboard & Analytics](#dashboard--analytics)
7. [Technical Features](#technical-features)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The AI-Powered Invoice Auditor is an intelligent document processing system that automates invoice data extraction, validation, and auditing using Google's Gemini AI. The system provides a complete workflow from upload to approval with built-in fraud detection, duplicate checking, and anomaly detection.

### Key Capabilities
- **Automated Data Extraction**: AI extracts vendor name, date, amounts, currency, and line items from invoices
- **Intelligent Validation**: Detects math errors, duplicates, and anomalies automatically
- **Multi-User Workflow**: Role-based access with AP Clerk, Finance Manager, and Auditor roles
- **Audit Trail**: Complete change tracking and edit history for compliance
- **Risk Assessment**: Automatic risk scoring based on multiple factors
- **Vendor Intelligence**: Historical analysis and anomaly detection per vendor

---

## Getting Started

### System Requirements
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection
- Supported invoice formats: PDF, PNG, JPG, JPEG

### Initial Setup

1. **Environment Configuration**
   - The system requires a `.env` file with the following keys:
   ```
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   GOOGLE_API_KEY=your_gemini_api_key
   GOOGLE_API_KEY_2=optional_second_key
   GOOGLE_API_KEY_3=optional_third_key
   ```

2. **Database Setup**
   - Supabase tables required:
     - `invoices`: Main invoice records
     - `vendors`: Vendor history and statistics
     - `invoice_edits`: Audit log of changes
     - `invoice_audits`: Final audit records
   - Storage bucket: `invoices` (for file storage)

3. **Launch Application**
   ```bash
   streamlit run app.py
   ```

---

## User Roles & Permissions

The system implements Role-Based Access Control (RBAC) with three distinct user roles:

### 1. AP Clerk (Accounts Payable Clerk)
**Primary Role**: Data entry and initial invoice processing

**Permissions**:
- ✅ Upload invoices
- ✅ Edit extracted data
- ✅ Mark invoices as "Reviewed"
- ✅ View their own activity summary
- ❌ Cannot approve invoices
- ❌ Cannot perform audits
- ❌ Limited dashboard access

**Typical Workflow**:
1. Upload invoice documents
2. Verify AI-extracted data
3. Make corrections if needed
4. Submit for manager approval

---

### 2. Finance Manager
**Primary Role**: Review, approve/reject invoices, and monitor operations

**Permissions**:
- ✅ Upload invoices
- ✅ Edit extracted data
- ✅ Review invoices
- ✅ **Approve or Reject** invoices
- ✅ Access full operations dashboard
- ✅ View analytics and reports
- ✅ Export data
- ❌ Cannot perform final audits

**Typical Workflow**:
1. Review invoices submitted by AP Clerk
2. Verify flagged items and risk assessments
3. Approve legitimate invoices
4. Reject fraudulent or invalid invoices
5. Monitor SLA performance and operational metrics

---

### 3. Auditor
**Primary Role**: Final verification and compliance review

**Permissions**:
- ✅ View all approved invoices
- ✅ Mark invoices as "Audited"
- ✅ Add audit notes
- ✅ Access full analytics dashboard
- ❌ Cannot upload invoices
- ❌ Cannot edit invoice data

**Typical Workflow**:
1. Review approved invoices in audit queue
2. Verify compliance and accuracy
3. Mark as audited with notes
4. Monitor audit completion rates

---

## Core Features

### 1. Invoice Upload & AI Processing

**How to Upload**:
1. Select your role in the sidebar
2. Click "Upload Invoice" section
3. Choose file (PDF, PNG, JPG, JPEG)
4. Click "Analyze Invoice"

**What Happens**:
- File uploaded to Supabase Storage
- AI extracts all data fields with confidence scores
- System validates mathematical accuracy
- Duplicate check performed automatically
- Anomaly detection runs against vendor history
- Risk score calculated
- Results displayed in review interface

**AI Extraction Fields**:
- Vendor Name (with location explanation)
- Invoice Date
- Currency
- Total Amount
- Line Items (description, quantity, unit price, total)
- Confidence scores for each field

---

### 2. Data Validation & Review Interface

**Validation Checks**:
1. **Math Validation**: Line items must sum to total amount
   - ✅ Pass: Green "Math Validates" badge
   - ❌ Fail: Red warning with difference amount

2. **Duplicate Detection**: Checks for existing invoices with same:
   - Vendor name
   - Invoice date
   - Total amount
   - Shows warning if duplicate found

3. **Anomaly Detection**: Compares to vendor history
   - Flags if amount is >2x historical average
   - Shows warning with comparison

**Editable Fields**:
- Vendor Name
- Invoice Date (date picker)
- Total Amount (numeric input)
- Currency (dropdown: USD, EUR, GBP, INR, etc.)
- Line Items (editable table):
  - Add rows with "+" button
  - Delete rows with "🗑️" button
  - Edit all fields inline

---

### 3. Risk Scoring System

**Risk Levels**:
- 🟢 **LOW RISK** (0-30 points): Standard processing
- 🟠 **MEDIUM RISK** (31-60 points): Requires attention
- 🔴 **HIGH RISK** (61+ points): Mandatory review

**Risk Factors** (each adds 20 points):
- ❌ Math does not validate
- ⚠️ Duplicate invoice detected
- 📈 Anomaly: Amount significantly higher than vendor history
- 🤖 Low AI confidence (<70%)

**Risk Score Display**:
- Shown as progress bar with color coding
- Detailed breakdown of risk factors
- Visible to all users during review

---

### 4. Approval Workflow

**Workflow Stages**:

```
UPLOADED → REVIEWED → APPROVED/REJECTED → AUDITED
```

**Stage Details**:

1. **🔵 UPLOADED**: Initial state after AI processing
   - Visible to all users with edit permissions
   - Can be edited and moved to "Reviewed"

2. **🟠 REVIEWED**: Clerk has verified the data
   - Data has been manually checked
   - Ready for manager approval
   - AP Clerk can mark as reviewed

3. **🟢 APPROVED**: Finance Manager has approved
   - Invoice is valid and ready for payment
   - Updates vendor history statistics
   - Moves to auditor queue
   - **Only Finance Manager can approve**

4. **🔴 REJECTED**: Finance Manager has rejected
   - Invoice is fraudulent or invalid
   - Does not update vendor history
   - Reason must be provided

5. **🟣 AUDITED**: Auditor has performed final check
   - Compliance verification complete
   - Audit trail logged
   - **Only Auditor can mark as audited**

---

### 5. Vendor Intelligence

**Historical Tracking**:
The system maintains a profile for each vendor including:
- Total number of invoices processed
- Average invoice value (running average)
- Last invoice date
- Number of flagged invoices

**Anomaly Detection**:
- Automatically flags invoices >2x vendor's historical average
- Example: If vendor typically sends $1,000 invoices, a $3,000 invoice triggers alert
- Helps detect fraud, data entry errors, or unusual charges

**Vendor Statistics Display**:
When reviewing an invoice, you'll see:
- Total invoices from this vendor
- Average amount
- Last invoice date
- Number of previously flagged invoices

---

### 6. Audit Trail & Edit Logging

**What Gets Logged**:
Every change to an invoice is recorded in the audit log:
- Field name changed
- Old value
- New value
- Timestamp (automatic)
- User who made the change (automatic)

**Changes Tracked**:
- Vendor name modifications
- Total amount adjustments
- Date corrections
- Line item edits (logged as "User Modified Table")

**Viewing Edit History**:
- Click "📜 Show Edit History" in the review interface
- Expandable section shows all changes in chronological order
- Useful for compliance audits and dispute resolution

---

### 7. Explainability & Confidence Scores

**AI Explainability**:
The AI provides explanations for where it found each field:
- Example: "Vendor Name: Found at top left logo"
- Example: "Total Amount: Bold text at bottom right"
- Example: "Invoice Date: Labelled 'Date' in top right"

**Confidence Scores**:
- Each field has a confidence score (0.0 to 1.0)
- Overall document confidence shown as percentage
- Low confidence (<70%) triggers "Uncertain Extraction" flag
- Helps users know which fields need extra attention

**Viewing Explanations**:
- Click "🔍 View AI Explanations" in the review interface
- Shows exactly where AI found each piece of data
- Helps verify AI accuracy and understand extraction logic

---

## Workflow Guide

### Scenario 1: AP Clerk Processing New Invoice

1. **Login as AP_CLERK** in sidebar

2. **Upload Invoice**:
   - Click "Upload File" in sidebar
   - Select invoice document
   - Click "Analyze Invoice"
   - Wait for AI processing (10-30 seconds)

3. **Review Extracted Data**:
   - Check vendor name, date, total
   - Verify line items match document
   - Look for validation warnings:
     - Math errors (red warning)
     - Duplicate alerts (yellow warning)
     - Anomaly flags (orange warning)

4. **Make Corrections if Needed**:
   - Click in field to edit
   - Use date picker for dates
   - Add/remove line items with +/🗑️ buttons
   - Ensure math adds up correctly

5. **Submit for Review**:
   - Review risk score and flags
   - Add note if needed (optional)
   - Click "📋 Mark as Reviewed"
   - Invoice moves to Finance Manager queue

---

### Scenario 2: Finance Manager Reviewing Invoices

1. **Login as FINANCE_MANAGER** in sidebar

2. **Review Pending Invoices**:
   - Scroll to "🔍 Pending Invoices" section
   - See list of invoices in UPLOADED or REVIEWED stage
   - Click "👁️ View" on invoice to review

3. **Evaluate Invoice**:
   - Check risk score and level
   - Review any flags or warnings
   - Verify vendor statistics
   - Check edit history if applicable
   - Review AI confidence and explanations

4. **Make Decision**:

   **To Approve**:
   - Click "✅ Approve Invoice"
   - Invoice updates vendor history
   - Moves to auditor queue
   - Timestamp recorded

   **To Reject**:
   - Enter rejection reason in text box
   - Click "❌ Reject Invoice"
   - Invoice marked as rejected
   - Does not update vendor history

5. **Monitor Operations**:
   - Check "📈 Operations Control Center"
   - Review operational alerts
   - Monitor SLA performance
   - Export reports as needed

---

### Scenario 3: Auditor Final Review

1. **Login as AUDITOR** in sidebar

2. **Access Audit Dashboard**:
   - Scroll to "📋 Auditor Review Dashboard"
   - See two tabs:
     - **🆕 To Be Audited**: Approved invoices awaiting audit
     - **📁 Audited**: Previously audited invoices

3. **Review Pending Audits**:
   - In "To Be Audited" tab
   - Click "👁️ View" on invoice

4. **Perform Audit**:
   - Review all data for accuracy
   - Check compliance with policies
   - Verify vendor and amounts
   - Review risk assessment
   - Check approval trail

5. **Complete Audit**:
   - Add audit notes if needed
   - Click "🟣 Mark as Audited"
   - Audit record created in database
   - Invoice removed from pending queue

---

## Dashboard & Analytics

### Operations Control Center
**Available to**: Finance Manager, Auditor

**Operational Alerts**:
- 🔴 **High Risk Invoices**: Count of high-risk items needing attention
- ⚠️ **Low AI Confidence**: Invoices with <70% confidence
- ⏱️ **SLA Breaches**: Invoices in review >72 hours

**SLA Performance Metrics**:
- Average approval time (hours)
- Fastest approval time
- Slowest approval time
- Color-coded indicators (green = good, red = breach)

**Analytics Charts**:

1. **Risk Distribution**: Bar chart showing LOW/MEDIUM/HIGH risk counts
2. **Approval Funnel**: Flow from UPLOADED → REVIEWED → APPROVED → REJECTED
3. **Top Vendors**: Top 5 vendors by total invoice value
4. **AI Confidence Trend**: Daily average confidence scores over time

**Export Options**:
- 📥 Download Approved Invoices (CSV)
- 📥 Download Risk Report (CSV)

**Recent Transactions Table**:
- Last 10 invoices with SLA status
- Color-coded breach warnings
- Real-time updates

---

### My Activity Summary
**Available to**: AP Clerk

**Metrics Displayed**:
- Total invoices uploaded
- Pending review count
- Approved invoice count

**Purpose**: Simple overview for data entry users to track their work without overwhelming operational details

---

## Technical Features

### 1. Multi-Key API Management

**Round-Robin Scheduling**:
- System supports up to 9 Google Gemini API keys
- Automatically rotates through keys to maximize throughput
- Tracks failed keys and skips them

**API Key Status Display**:
Located in sidebar:
- 🔑 Total keys loaded
- ✅ Active key indicator
- 💤 Standby keys
- ❌ Quota exceeded keys
- Next key in rotation

**Daily Quota Reset**:
- System automatically detects new day (UTC)
- Resets all quota counters at midnight
- Re-enables previously exhausted keys

**Fallback Behavior**:
If all API keys are exhausted:
- System switches to demo data
- Warning displayed to user
- Processing continues without interruption
- Recommends adding more keys

---

### 2. Intelligent Caching

**Cache Features**:
- In-memory cache for processed invoices
- Uses MD5 hash of file bytes as key
- Instant results for re-uploaded files
- Persists during application session

**Benefits**:
- Eliminates redundant API calls
- Instant processing for duplicates
- Reduces API quota consumption
- Improves response time

**Cache Indicators**:
- "⚡ Using cached AI result" message when cache hit
- Hash displayed for verification

---

### 3. Error Handling & Retries

**Retry Logic**:
- 2 attempts per API key
- Automatic key rotation on quota errors
- 2-second delay between retries
- Detailed error logging

**Error Types Handled**:
- 429 Quota Exceeded → Try next key
- Transient network errors → Retry same key
- Non-retryable errors → Move to next key
- All keys failed → Demo fallback

---

### 4. Data Persistence

**Supabase Integration**:
- Real-time database for all invoice records
- Storage bucket for invoice files
- Automatic public URL generation
- Transaction support

**Database Schema**:

**invoices table**:
- Core invoice data
- AI extraction results
- Workflow status
- Risk assessment
- Approval trail
- Timestamps

**vendors table**:
- Vendor profiles
- Historical statistics
- Running averages
- Last invoice date

**invoice_edits table**:
- Field-level audit trail
- Old/new values
- Timestamps
- User tracking

**invoice_audits table**:
- Final audit records
- Auditor notes
- Compliance flags

---

### 5. File Storage & Management

**Upload Process**:
1. File uploaded to Supabase Storage bucket
2. Public URL generated
3. URL stored in database
4. File accessible for review

**Supported Formats**:
- PDF documents
- PNG images
- JPG/JPEG images

**File Display**:
- Embedded preview in review interface
- Direct link for full-size viewing
- File type indicators

---

## Troubleshooting

### Common Issues

#### Issue: "No GOOGLE_API_KEY found in .env file"
**Cause**: Missing or incorrectly configured .env file

**Solution**:
1. Create `.env` file in project root
2. Add at least one API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```
3. Restart application

---

#### Issue: "All API keys exhausted"
**Cause**: All configured API keys have hit daily quota limit

**Solutions**:
1. Add more API keys to `.env`:
   ```
   GOOGLE_API_KEY_2=another_key
   GOOGLE_API_KEY_3=yet_another_key
   ```
2. Wait for automatic daily reset (midnight UTC)
3. Use demo fallback data temporarily

**Monitoring**: Check sidebar "🔑 API Status" section to see key status

---

#### Issue: "Missing Supabase keys in .env file"
**Cause**: Supabase configuration incomplete

**Solution**:
Add to `.env` file:
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_anon_key_here
```

---

#### Issue: Math validation fails but totals appear correct
**Cause**: Rounding differences or hidden line items

**Solutions**:
1. Check all line items are included
2. Verify unit price × quantity = total price for each row
3. Look for rounding issues (cents)
4. Check if tax is separate line item
5. Recalculate manually if needed

---

#### Issue: Duplicate warning but invoice is new
**Cause**: Another invoice with identical vendor, date, and amount

**Solutions**:
1. Check dashboard for existing matching invoice
2. Verify this is truly a duplicate (sometimes vendors send same amount)
3. If legitimate, proceed with review noting it's not a duplicate
4. Consider adjusting duplicate detection threshold if frequent

---

#### Issue: Anomaly flag on legitimate large invoice
**Cause**: Invoice significantly higher than vendor's historical average

**Solutions**:
1. Review vendor statistics to see historical average
2. Verify invoice is legitimate (large order, special project, etc.)
3. Add note explaining the anomaly
4. Proceed with approval if valid
5. Note: Anomaly detection is a flag, not a blocker

---

#### Issue: Low AI confidence on clear invoice
**Cause**: Poor image quality, unusual format, or handwritten elements

**Solutions**:
1. Review AI explanations to see what was unclear
2. Manually verify all extracted fields
3. Re-upload with higher quality scan if available
4. Make corrections in review interface
5. Proceed with manual verification

---

#### Issue: Cannot approve invoice as AP Clerk
**Cause**: Role-based permissions - AP Clerks cannot approve

**Solution**:
1. Mark invoice as "Reviewed" instead
2. Finance Manager will see it in pending queue
3. Manager can then approve or reject
4. This is by design for proper segregation of duties

---

#### Issue: File upload fails or times out
**Causes**: Network issues, file too large, unsupported format

**Solutions**:
1. Check file format (must be PDF, PNG, JPG, or JPEG)
2. Verify file size is reasonable (<10MB recommended)
3. Check internet connection
4. Try refreshing page and re-uploading
5. Verify Supabase Storage bucket is configured

---

### Performance Tips

1. **Optimize API Usage**:
   - Configure multiple API keys for high-volume processing
   - Monitor API status in sidebar
   - Process invoices in batches during off-peak hours

2. **Improve AI Accuracy**:
   - Use high-quality scans (300 DPI or higher)
   - Ensure good contrast and lighting
   - Avoid blurry or skewed images
   - Use native PDFs when possible

3. **Efficient Workflow**:
   - Train users on their specific role workflows
   - Review high-risk invoices first
   - Use batch export for reporting
   - Monitor SLA metrics regularly

4. **Data Quality**:
   - Establish vendor naming conventions
   - Verify dates are in correct format
   - Double-check currency codes
   - Validate math before submission

---

## Security & Compliance

### Access Control
- Role-based permissions enforced
- Audit trail for all changes
- User attribution on all actions
- Segregation of duties (AP Clerk cannot approve)

### Data Integrity
- Complete edit history logged
- No data deletion (archive only)
- Timestamp all actions
- Preserve original AI extraction

### Compliance Features
- Full audit trail
- Change logging
- Approval workflow
- Final auditor review
- Export capabilities for external audits

---

## Support & Feedback

### Getting Help
1. Review this documentation
2. Check troubleshooting section
3. Contact your system administrator
4. Review audit logs for specific issues

### Best Practices
- Upload high-quality invoice images
- Review AI extractions carefully
- Document unusual circumstances in notes
- Monitor dashboard metrics regularly
- Export reports for record-keeping

---

## Appendix: Technical Specifications

### System Architecture
- **Frontend**: Streamlit web application
- **AI Engine**: Google Gemini (gemini-flash-latest)
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Caching**: In-memory Python dict

### API Configuration
- Model: gemini-flash-latest
- Round-robin key rotation
- 2 retries per key
- Daily quota auto-reset
- Demo fallback on exhaustion

### Validation Rules
- Math validation: Line items must sum to total (exact match)
- Duplicate detection: Match on vendor + date + amount
- Anomaly threshold: >2x vendor average
- Low confidence: <70% overall score
- Risk scoring: 0-100 scale, 20 points per factor

### Database Schema Summary
- **invoices**: Main records with workflow status
- **vendors**: Historical profiles and statistics
- **invoice_edits**: Field-level change log
- **invoice_audits**: Final audit records

---

*Last Updated: February 2026*  
*Version: 1.0*  
*Application: AI-Powered Invoice Auditor*

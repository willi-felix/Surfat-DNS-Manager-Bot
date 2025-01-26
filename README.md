# Surfat - DNS Manager Discord Bot
**Surfat - DNS Manager Discord Bot** - An open-source project built on Cloudflare and Discord, designed to develop a Discord Bot capable of managing and executing actions associated with a specific domain on Cloudflare.

## Features
1. **Latency Check**  
   - Provides real-time latency information using the `/ping` command.
2. **DNS Record Management**  
   - Create DNS records (`/create_record`) with validation for record types (`A`, `AAAA`, `CNAME`, `NS`).  
   - Delete existing DNS records (`/delete_record`).  
   - Approve pending DNS records (`/approve`) with integration to Cloudflare.  
   - View all DNS records with options for paginated results and admin privileges (`/view_records`).  
3. **Garbage Collector**  
   - Automatically deletes unapproved DNS records older than 7 days (`/garbage_collector`).  
4. **User Reminder**  
   - Sends reminders to users with pending DNS records that have been inactive for more than 3 days (`/reminder`).  
5. **Help Menu**  
   - Provides a detailed command list and usage guide for the bot (`/help`).  
6. **Admin Features**  
   - Logs significant actions (e.g., record creation, deletion, and approval) to a dedicated channel.  
   - Ensures only users with proper permissions can approve or manage sensitive commands.  
7. **Cloudflare Integration**  
   - Communicates with the Cloudflare API to manage DNS records dynamically.  
   - Validates and updates DNS data within Cloudflare.  
8. **Database Management**  
   - Utilizes SQLiteCloud for persistent storage of DNS records.  
   - Features dynamic schema adjustments and connection pooling.
## How to use
### Add variables in the source code
*1.* SQLiteCloud database with variable ```SQLITECLOUD_CONNECTION_STRING```
Go to https://sqlitecloud.io, create an account and create a Project, then create a New Database, after creating it as {database_name}.sqlite. Then, click the Connect button and select the newly created Database and click the Copy button in the Connection String line

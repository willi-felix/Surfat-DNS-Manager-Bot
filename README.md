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
*1.* **SQLiteCloud database with variable ```SQLITECLOUD_CONNECTION_STRING```**
Go to https://sqlitecloud.io, create an account and create a Project, then create a New Database, after creating it as {database_name}.sqlite. Then, click the Connect button and select the newly created Database and click the Copy button in the Connection String line and add that segment into the source code.

*2.* **Discord Token with variable ```TOKEN```**
Go to https://discord.com/developers, create a new bot, then go to the Bot tab and enable `Public Bot`, `Presence Intent`, `Server Members Intent` and `Message Content Intent`. Then scroll up and click Reset Token to get a new Token and add it to the source code.

*3.* **Setting Up Cloudflare Variables (CF_API_KEY and ZONE_ID)**
1. *Log in to Cloudflare Dashboard*
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) and log in to your account.
2. *Select a Domain*
   - Choose the domain you want to manage.
3. *Retrieve API Key*
   - Navigate to [API Tokens Page](https://dash.cloudflare.com/profile/api-tokens).  
   - Click **Create Token**.  
   - Select the **Edit Zone DNS** template (or customize permissions to allow only DNS editing for the desired domain).  
   - Ensure the permissions are set to:  
     - **Zone**: **Edit**  
     - **Zone Resources**: **Include specific zone** and select the domain.  
   - Click **Continue to Summary**, then **Create Token**.  
   - Copy the generated token and assign it to the `CF_API_KEY` variable in your source code.
4. *Retrieve Zone ID*
   - Go to the **Overview** tab of the selected domain.  
   - Scroll down to find the **Zone ID**.  
   - Copy the Zone ID and assign it to the `ZONE_ID` variable in your source code.
  
**⚠️ Important: Use the API Token instead of the API Key for better security and restricted permissions. Keep your token and Zone ID confidential to prevent unauthorized access.**

*4.* **The variable ```LOG CHANNEL ID``` is a variable used to store logos for bots to create (record creation request, approval action, record deletion action)**

*5.* **The variable ```ADMIN_ROLE_ID``` is the role with the highest authority in the bot (approve record, delete all other records, garbage collection, reminder), in this role you have the highest authority.**

*Note: It is not required to be the Administrator role, any role, you just need to change it in Bot*

**⚠️ Important: Please provide it to people you trust because it may affect records in your Zone. Do not distribute this role to members of your Discord server**

### Launch
*1.* Launch the bot to test its operation

*2.* Launch bot on a server 24/7 (Recommended)

*Suggest: [PylexNodes](https://pylexnodes.net), Free Python Hosting*
- 512MB RAM
- 0.2 Core
- Uptime 24/7
- Without renew

*If you have problems with the bot or get stuck, visit [Surfat's Discord](https://discord.gg/48yfNKeaAX) to get help as soon as possible.*

**Sincerely thank Cloudflare for providing a hosting service and providing API for us to complete this source code. Once again, thank you very much**

© Copyright 2025 William Felix. Apache License 2.0. All rights reserved.  
See https://www.apache.org/licenses/LICENSE-2.0 for details.

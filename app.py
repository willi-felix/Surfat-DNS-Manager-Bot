import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
import sqlitecloud
import requests
import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

TOKEN = 'YOUR_DISCORD_TOKEN'
CF_API_URL = 'https://api.cloudflare.com/client/v4/zones' # Do not edit under any circumstances, to avoid inactivity
CF_API_KEY = 'YOUR_CLOUDFLARE_API_KEY'
CF_EMAIL = 'YOUR-CLOUDFLARE_EMAIL'
ZONE_ID = 'YOUR_CLOUDFLARE_ZONE_ID'

LOG_CHANNEL_ID = YOUR LOG_CHANNEL_ID
ADMIN_ROLE_ID = YOUR_ADMIN_ROLE_ID

class DatabaseManager:
    def __init__(self):
        self.connection_pool = []
        self.pool_lock = asyncio.Lock()
        self.max_connections = 5
        self.db_url = "SQLITECLOUD_CONNECTION_STRING"
        self.ensure_table_schema()

    def ensure_table_schema(self):
        with sqlitecloud.connect(self.db_url) as conn:
            cursor = conn.cursor()
            schema = """
            CREATE TABLE IF NOT EXISTS records (
                userid TEXT NOT NULL,
                record_name TEXT NOT NULL,
                record_type TEXT NOT NULL,
                content TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            cursor.execute(schema)
            try:
                cursor.execute("SELECT created_at FROM records LIMIT 1")
            except sqlitecloud.exceptions.SQLiteCloudOperationalError:
                cursor.execute("ALTER TABLE records ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            conn.commit()

    async def get_connection(self):
        async with self.pool_lock:
            if not self.connection_pool:
                try:
                    conn = sqlitecloud.connect(self.db_url)
                    self.connection_pool.append(conn)
                except Exception as e:
                    print(f"Failed to create new connection: {e}")
                    return None
            return self.connection_pool.pop() if self.connection_pool else None

    async def release_connection(self, conn):
        async with self.pool_lock:
            if len(self.connection_pool) < self.max_connections:
                self.connection_pool.append(conn)
            else:
                conn.close()

    @asynccontextmanager
    async def connection(self):
        conn = await self.get_connection()
        try:
            yield conn
        finally:
            if conn:
                await self.release_connection(conn)

    async def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List]:
        async with self.connection() as conn:
            if not conn:
                raise Exception("Could not establish database connection")
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                if fetch:
                    return cursor.fetchall()
                return cursor
            except Exception as e:
                print(f"Query execution error: {e}")
                raise

class DNSBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        try:
            try:
                latency = round(self.bot.latency * 1000, 2)
                status = "Normal" if latency < 200 else "High"
                color = discord.Color.green() if latency < 200 else discord.Color.orange()
            except:
                latency = -1
                status = "Error"
                color = discord.Color.red()

            embed = discord.Embed(
                title="Pong! 🏓",
                color=color,
                timestamp=datetime.datetime.utcnow()
            )
            
            if latency >= 0:
                embed.add_field(
                    name="Latency",
                    value=f"`{latency}ms` ({status})",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="Failed to check latency",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except discord.errors.NotFound:
            return
        except discord.errors.HTTPException as he:
            print(f"HTTP Error in ping command: {he}")
            return
        except Exception as e:
            print(f"Unexpected error in ping command: {str(e)}")
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "An unexpected error occurred while processing the command.",
                        ephemeral=True
                    )
                except:
                    pass

    @app_commands.command(name="create_record", description="Create a DNS record")
    async def create_record(self, interaction: discord.Interaction, record_name: str, record_type: str, content: str):
        try:
            record_type = record_type.upper()
            record_name = record_name.strip().lower()
            content = content.strip()

            if record_type not in ["A", "AAAA", "CNAME", "NS"]:
                await interaction.response.send_message(
                    "Invalid record type. Supported types: A, AAAA, CNAME, NS.",
                    ephemeral=True
                )
                return

            content_valid = True
            error_message = ""

            if record_type == "A":
                ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                if not re.match(ip_pattern, content):
                    content_valid = False
                    error_message = "Invalid IPv4 address format. Example: 192.168.1.1"
                else:
                    octets = content.split('.')
                    for octet in octets:
                        if not (0 <= int(octet) <= 255):
                            content_valid = False
                            error_message = "IPv4 address octets must be between 0 and 255"
                            break

            elif record_type == "AAAA":
                try:
                    ipaddress.IPv6Address(content)
                except ValueError:
                    content_valid = False
                    error_message = "Invalid IPv6 address format. Example: 2001:0db8:85a3:0000:0000:8a2e:0370:7334"

            elif record_type in ["CNAME", "NS"]:
                domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
                if not re.match(domain_pattern, content):
                    content_valid = False
                    error_message = f"Invalid domain format for {record_type} record. Example: example.com"

            if not content_valid:
                error_embed = discord.Embed(
                    title="Content Validation Error",
                    description=error_message,
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                error_embed.add_field(
                    name="Record Type Format",
                    value=f"Format for {record_type} record:\n" + {
                        "A": "IPv4 address (e.g., 192.168.1.1)",
                        "AAAA": "IPv6 address (e.g., 2001:0db8:85a3:0000:0000:8a2e:0370:7334)",
                        "CNAME": "Domain name (e.g., example.com)",
                        "NS": "Nameserver domain (e.g., ns1.example.com)"
                    }[record_type],
                    inline=False
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            await interaction.response.send_message(
                "Processing your record creation request..."
            )

            try:
                existing = await self.db.execute_query(
                    "SELECT record_name FROM records WHERE LOWER(record_name) = ? AND userid = ?",
                    (record_name, str(interaction.user.id))
                )

                if existing:
                    await interaction.edit_original_response(
                        content="You already have a pending record with this name."
                    )
                    return

                await self.db.execute_query(
                    """INSERT INTO records 
                       (userid, record_name, record_type, content, approved, created_at) 
                       VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)""",
                    (str(interaction.user.id), record_name, record_type, content)
                )

                embed = discord.Embed(
                    title="Record Created Successfully",
                    description="Your record has been created and is pending approval.",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Record Name", value=f"`{record_name}`", inline=True)
                embed.add_field(name="Type", value=f"`{record_type}`", inline=True)
                embed.add_field(name="Content", value=f"`{content}`", inline=True)
                embed.add_field(
                    name="Status",
                    value="⏳ Pending Approval",
                    inline=False
                )
                embed.set_footer(text=f"Requested by {interaction.user.name}")

                await interaction.edit_original_response(content=None, embed=embed)

                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"Record created: ``{record_name}`` ``({record_type})`` -> ``{content}`` by <@{interaction.user.id}>"
                    )

            except Exception as db_error:
                error_embed = discord.Embed(
                    title="Database Error",
                    description=f"Failed to create record: {str(db_error)}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(content=None, embed=error_embed)
                print(f"Database error in create_record: {str(db_error)}")

        except discord.errors.NotFound:
            return
        except Exception as e:
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed)
                else:
                    await interaction.edit_original_response(content=None, embed=error_embed)
            except:
                print(f"Critical error in create_record: {str(e)}")

    @app_commands.command(name="delete_record", description="Delete a DNS record")
    async def delete_record(self, interaction: discord.Interaction, record_name: str):
        try:
            await interaction.response.send_message(
                f"Processing deletion request for record: `{record_name}`..."
            )

            record_name = record_name.strip().lower()

            try:
                record = await self.db.execute_query(
                    "SELECT userid, approved, record_type, content FROM records WHERE LOWER(record_name) = ?",
                    (record_name,)
                )

                if not record:
                    await interaction.edit_original_response(
                        content="This record does not exist in the database."
                    )
                    return

                record_owner_id, approved, record_type, content = record[0]

                if approved == 0:
                    await interaction.edit_original_response(
                        content="This record has not been approved yet and cannot be deleted."
                    )
                    return

                has_permission = (str(interaction.user.id) == record_owner_id or 
                                any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles))
                
                if not has_permission:
                    await interaction.edit_original_response(
                        content="You do not have permission to delete this record."
                    )
                    return

                try:
                    headers = {
                        "Authorization": f"Bearer {CF_API_KEY}",
                        "X-Auth-Email": CF_EMAIL
                    }
                    
                    cf_response = requests.get(
                        f"{CF_API_URL}/{ZONE_ID}/dns_records",
                        headers=headers
                    ).json()

                    record_id = next(
                        (r["id"] for r in cf_response["result"] 
                         if r["name"] == f"{record_name}.is-app.top"),
                        None
                    )

                    if not record_id:
                        await interaction.edit_original_response(
                            content="Record not found in Cloudflare. Please contact an admin for assistance."
                        )
                        return

                    delete_response = requests.delete(
                        f"{CF_API_URL}/{ZONE_ID}/dns_records/{record_id}",
                        headers=headers
                    )

                    if delete_response.status_code != 200:
                        error_data = delete_response.json()
                        await interaction.edit_original_response(
                            content=f"Failed to delete record in Cloudflare: {error_data.get('errors', ['Unknown error'])[0]}"
                        )
                        return

                except requests.RequestException as cf_error:
                    await interaction.edit_original_response(
                        content=f"Failed to communicate with Cloudflare: {str(cf_error)}"
                    )
                    return

                await self.db.execute_query(
                    "DELETE FROM records WHERE LOWER(record_name) = ?",
                    (record_name,)
                )

                embed = discord.Embed(
                    title="Record Deleted Successfully",
                    description=f"The record has been removed from both Cloudflare and the database.",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Record Name", value=f"`{record_name}`", inline=True)
                embed.add_field(name="Type", value=f"`{record_type}`", inline=True)
                embed.add_field(name="Content", value=f"`{content}`", inline=True)
                embed.set_footer(text=f"Deleted by {interaction.user.name}")

                await interaction.edit_original_response(content=None, embed=embed)

                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"Record deleted: ``{record_name}`` by <@{interaction.user.id}>"
                    )

            except Exception as db_error:
                error_embed = discord.Embed(
                    title="Database Error",
                    description=f"Failed to delete record: {str(db_error)}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(content=None, embed=error_embed)
                print(f"Database error in delete_record: {str(db_error)}")

        except discord.errors.NotFound:
            return
        except Exception as e:
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed)
                else:
                    await interaction.edit_original_response(content=None, embed=error_embed)
            except:
                print(f"Critical error in delete_record: {str(e)}")

    @app_commands.command(name="approve", description="Approve a DNS record")
    async def approve(self, interaction: discord.Interaction, record_name: str):
        try:
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message(
                    "You do not have permission to approve records.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"Processing approval for record: `{record_name}`...",
                ephemeral=True
            )

            record_name = record_name.strip().lower()

            try:
                record = await self.db.execute_query(
                    """SELECT record_name, record_type, content, userid 
                       FROM records 
                       WHERE LOWER(record_name) = ? AND approved = 0""",
                    (record_name,)
                )

                if not record:
                    await interaction.edit_original_response(
                        content="Record not found or already approved."
                    )
                    return

                record_name, record_type, content, record_owner_id = record[0]

                headers = {
                    "Authorization": f"Bearer {CF_API_KEY}",
                    "X-Auth-Email": CF_EMAIL,
                    "Content-Type": "application/json"
                }
                payload = {
                    "type": record_type,
                    "name": f"{record_name}.is-app.top",
                    "content": content,
                    "ttl": 1
                }

                try:
                    response = requests.post(
                        f"{CF_API_URL}/{ZONE_ID}/dns_records",
                        json=payload,
                        headers=headers
                    )

                    if response.status_code != 200:
                        error_data = response.json()
                        await interaction.edit_original_response(
                            content=f"Failed to create record in Cloudflare: {error_data.get('errors', ['Unknown error'])[0]}"
                        )
                        return

                except requests.RequestException as cf_error:
                    await interaction.edit_original_response(
                        content=f"Failed to communicate with Cloudflare: {str(cf_error)}"
                    )
                    return

                await self.db.execute_query(
                    "UPDATE records SET approved = 1 WHERE LOWER(record_name) = ?",
                    (record_name,)
                )

                embed = discord.Embed(
                    title="Record Approved Successfully",
                    description=f"Record `{record_name}` has been approved and created in Cloudflare.",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.add_field(name="Record Name", value=f"`{record_name}`", inline=True)
                embed.add_field(name="Type", value=f"`{record_type}`", inline=True)
                embed.add_field(name="Content", value=f"`{content}`", inline=True)
                embed.set_footer(text=f"Approved by {interaction.user.name}")

                await interaction.edit_original_response(content=None, embed=embed)

                try:
                    user = await self.bot.fetch_user(record_owner_id)
                    if user:
                        user_embed = discord.Embed(
                            title="DNS Record Approved",
                            description=f"Your DNS record has been approved and created in Cloudflare.",
                            color=discord.Color.green(),
                            timestamp=datetime.datetime.utcnow()
                        )
                        user_embed.add_field(name="Record Name", value=f"`{record_name}`", inline=True)
                        user_embed.add_field(name="Type", value=f"`{record_type}`", inline=True)
                        user_embed.add_field(name="Content", value=f"`{content}`", inline=True)
                        await user.send(embed=user_embed)
                except Exception as user_error:
                    print(f"Failed to notify user {record_owner_id}: {str(user_error)}")

                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"Record approved: ``{record_name}`` ``({record_type})`` -> ``{content}`` by <@{interaction.user.id}>"
                    )

            except Exception as db_error:
                error_embed = discord.Embed(
                    title="Database Error",
                    description=f"Failed to approve record: {str(db_error)}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(content=None, embed=error_embed)
                print(f"Database error in approve command: {str(db_error)}")

        except discord.errors.NotFound:
            return
        except Exception as e:
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await interaction.edit_original_response(content=None, embed=error_embed)
            except:
                print(f"Critical error in approve command: {str(e)}")

    @app_commands.command(name="view_records", description="View all DNS records")
    async def view_records(self, interaction: discord.Interaction):
        try:
            is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
            
            await interaction.response.send_message(
                "Fetching records...",
                ephemeral=True
            )

            try:
                if is_admin:
                    query = """
                    SELECT record_name, record_type, content, approved, userid, created_at 
                    FROM records 
                    ORDER BY created_at DESC
                    """
                    records = await self.db.execute_query(query)
                else:
                    query = """
                    SELECT record_name, record_type, content, created_at 
                    FROM records 
                    WHERE userid = ? AND approved = 1
                    ORDER BY created_at DESC
                    """
                    records = await self.db.execute_query(query, (str(interaction.user.id),))

                if not records:
                    embed = discord.Embed(
                        title="No Records Found",
                        description="You don't have any DNS records yet." if not is_admin else "No DNS records available in the database.",
                        color=discord.Color.light_grey(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    await interaction.edit_original_response(content=None, embed=embed)
                    return

                records_per_page = 10
                pages = [records[i:i + records_per_page] for i in range(0, len(records), records_per_page)]
                current_page = 0

                def create_page_embed(page_records, page_num):
                    embed = discord.Embed(
                        title="DNS Records" if not is_admin else "All DNS Records (Admin View)",
                        description=f"Page {page_num + 1} of {len(pages)}",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    
                    for record in page_records:
                        if is_admin:
                            record_name, record_type, content, approved, userid, created_at = record
                            status = "✅ Approved" if approved else "⏳ Pending"
                            embed.add_field(
                                name=f"📝 {record_name}",
                                value=f"""
                                **Type:** `{record_type}`
                                **Content:** `{content}`
                                **Status:** {status}
                                **User:** <@{userid}>
                                **Created:** {created_at}
                                """,
                                inline=False
                            )
                        else:
                            record_name, record_type, content, created_at = record
                            embed.add_field(
                                name=f"📝 {record_name}",
                                value=f"""
                                **Type:** `{record_type}`
                                **Content:** `{content}`
                                **Created:** {created_at}
                                """,
                                inline=False
                            )

                    embed.set_footer(text=f"Requested by {interaction.user.name}")
                    return embed

                embed = create_page_embed(pages[current_page], current_page)
                await interaction.edit_original_response(content=None, embed=embed)

                message = await interaction.original_response()
                if len(pages) > 1:
                    await message.add_reaction("⬅️")
                    await message.add_reaction("➡️")

                    def check(reaction, user):
                        return user == interaction.user and str(reaction.emoji) in ["⬅️", "➡️"] and reaction.message.id == message.id

                    while True:
                        try:
                            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)

                            if str(reaction.emoji) == "➡️" and current_page < len(pages) - 1:
                                current_page += 1
                                embed = create_page_embed(pages[current_page], current_page)
                                await message.edit(embed=embed)
                            elif str(reaction.emoji) == "⬅️" and current_page > 0:
                                current_page -= 1
                                embed = create_page_embed(pages[current_page], current_page)
                                await message.edit(embed=embed)

                            await message.remove_reaction(reaction, user)
                        except asyncio.TimeoutError:
                            try:
                                await message.clear_reactions()
                            except:
                                pass
                            break

            except Exception as db_error:
                error_embed = discord.Embed(
                    title="Database Error",
                    description=f"Failed to fetch records: {str(db_error)}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(content=None, embed=error_embed)
                print(f"Database error in view_records: {str(db_error)}")

        except discord.errors.NotFound:
            return
        except Exception as e:
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await interaction.edit_original_response(content=None, embed=error_embed)
            except:
                print(f"Critical error in view_records: {str(e)}")

    @app_commands.command(name="garbage_collector", description="Clean up unapproved records (Admin only)")
    async def garbage_collector(self, interaction: discord.Interaction):
        try:
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message(
                    "You do not have permission to run this command.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                "Running garbage collector...",
                ephemeral=True
            )

            try:
                count_query = """
                SELECT COUNT(*) 
                FROM records 
                WHERE approved = 0 
                AND created_at < DATETIME('now', '-7 day')
                """
                count_result = await self.db.execute_query(count_query)
                records_to_delete = count_result[0][0] if count_result else 0

                delete_query = """
                DELETE FROM records
                WHERE approved = 0 
                AND created_at < DATETIME('now', '-7 day')
                RETURNING record_name, record_type, content, userid, created_at
                """
                deleted_records = await self.db.execute_query(delete_query)

                embed = discord.Embed(
                    title="🗑️ Garbage Collector Results",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )

                if records_to_delete > 0:
                    embed.description = f"""
                    Successfully cleaned up {len(deleted_records)} unapproved records older than 7 days.
                    
                    **Deleted Records Summary:**
                    """
                    
                    for i, record in enumerate(deleted_records[:10]):
                        record_name, record_type, content, userid, created_at = record
                        embed.add_field(
                            name=f"Record {i+1}",
                            value=f"""
                            **Name:** `{record_name}`
                            **Type:** `{record_type}`
                            **Owner:** <@{userid}>
                            **Created:** {created_at}
                            """,
                            inline=False
                        )
                    
                    if len(deleted_records) > 10:
                        embed.add_field(
                            name="Note",
                            value=f"... and {len(deleted_records) - 10} more records",
                            inline=False
                        )
                else:
                    embed.description = "No records found that meet the cleanup criteria."
                    embed.color = discord.Color.blue()

                embed.set_footer(text=f"Executed by {interaction.user.name}")

                await interaction.edit_original_response(content=None, embed=embed)

                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    log_embed = discord.Embed(
                        title="Garbage Collector Executed",
                        description=f"""
                        🗑️ Cleanup performed by <@{interaction.user.id}>
                        📊 Records deleted: {len(deleted_records)}
                        📅 Cutoff date: {(datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')}
                        """,
                        color=discord.Color.orange(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    await log_channel.send(embed=log_embed)

            except Exception as db_error:
                error_embed = discord.Embed(
                    title="Database Error",
                    description=f"Failed to run garbage collector: {str(db_error)}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(content=None, embed=error_embed)
                print(f"Database error in garbage_collector: {str(db_error)}")

        except discord.errors.NotFound:
            return
        except Exception as e:
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await interaction.edit_original_response(content=None, embed=error_embed)
            except:
                print(f"Critical error in garbage_collector: {str(e)}")

    @app_commands.command(name="reminder", description="Send reminder to users with pending records (Admin only)")
    async def reminder(self, interaction: discord.Interaction):
        try:
            if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                await interaction.response.send_message(
                    "You do not have permission to run this command.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                "Processing reminders... Please wait.",
                ephemeral=True
            )

            try:
                pending_records = await self.db.execute_query("""
                    SELECT userid, record_name, created_at 
                    FROM records 
                    WHERE approved = 0 AND created_at < DATETIME('now', '-3 day')
                """)

                sent_count = 0
                failed_count = 0

                for record in pending_records:
                    try:
                        user_id, record_name, created_at = record
                        user = await self.bot.fetch_user(user_id)
                        if user:
                            await user.send(
                                f"Reminder: Your DNS record `{record_name}` has been pending for approval since {created_at}. Please check."
                            )
                            sent_count += 1
                    except Exception as user_error:
                        failed_count += 1
                        print(f"Failed to send reminder to user {user_id}: {str(user_error)}")

                embed = discord.Embed(
                    title="Reminder Status",
                    color=discord.Color.green() if sent_count > 0 else discord.Color.orange()
                )
                
                if sent_count > 0 or failed_count > 0:
                    embed.description = f"""
                    📤 Reminders sent: {sent_count}
                    ❌ Failed to send: {failed_count}
                    📅 Total pending records: {len(pending_records)}
                    """
                else:
                    embed.description = "No pending records found requiring reminders."

                embed.set_footer(text=f"Executed by {interaction.user.name} | {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
                
                await interaction.edit_original_response(embed=embed)

            except Exception as db_error:
                error_embed = discord.Embed(
                    title="Database Error",
                    description=f"Failed to fetch pending records: {str(db_error)}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=error_embed)

        except discord.errors.NotFound:
            return
        except Exception as e:
            try:
                error_embed = discord.Embed(
                    title="Error",
                    description=f"An unexpected error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await interaction.edit_original_response(embed=error_embed)
            except:
                print(f"Critical error in reminder command: {str(e)}")

    @app_commands.command(name="help", description="List all available commands")
    async def help_command(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="🤖 Help Menu",
                description="""
                **Commands List**
                🏓 /ping - Check the bot's latency
                📝 /create_record - Create a new DNS record
                🗑️ /delete_record - Delete your DNS record
                👀 /view_records - View your DNS records

                **Usage Tips**
                • All commands use slash (/) prefix
                • Record names should be unique
                • Supported record types: A, AAAA, CNAME, NS
                • Records pending for >7 days are automatically removed

                **Support**
                Need help? Contact <@1247715728141058073>
                """.strip(),
                color=discord.Color.blue()
            )

            embed.set_footer(text="Help Menu")

            try:
                await interaction.response.send_message(embed=embed)
            except discord.errors.NotFound:
                await interaction.followup.send(embed=embed)
            except Exception as e:
                print(f"Error sending help message: {str(e)}")

        except Exception as e:
            print(f"Help command error: {str(e)}")
            try:
                await interaction.response.send_message("An error occurred while displaying the help message. Please try again.", ephemeral=True)
            except:
                pass

class DNSBotApp(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            case_insensitive=True
        )

    async def setup_hook(self):
        await self.add_cog(DNSBot(self))
        await self.tree.sync()

    async def on_ready(self):
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Managing DNS Records")
        )
        print(f"Logged in as {self.user}")

bot = DNSBotApp()

if __name__ == "__main__":
    bot.run(TOKEN)
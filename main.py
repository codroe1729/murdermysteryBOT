import discord
from discord.ext import commands
import asyncio

# intentsの設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# ★設定エリア
# ==========================================
TOKEN = "YOUR_BOT_TOKEN_HERE"      # Botのトークン
CATEGORY_NAME = "マダミス会場"       # カテゴリー名
MAIN_VC_NAME = "集合場所"              # 集合場所VC名
GM_ROLE_NAME = "GM"                # GMロール名
SUB_GM_ROLE_NAME = "GMsub"         # サブGMロール名
GM_TEXT_CHANNEL_NAME = "gm控室"     # GM専用ch（非公開）
GENERAL_TEXT_CHANNEL_NAME = "全体議論" # 全員用ch（公開）
SECRET_VC_NAMES = ["密談1", "密談2"]   # 密談用VC（公開）
# ==========================================

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました！')

# ---------------------------------------------------------
# 機能0：サブGM設定
# ---------------------------------------------------------
@bot.command()
async def setsub(ctx, member: discord.Member):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=SUB_GM_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=SUB_GM_ROLE_NAME, color=discord.Color.orange(), hoist=True)
            await ctx.send(f"🆕 ロール「{SUB_GM_ROLE_NAME}」を作成しました。")
        except:
            return
    await member.add_roles(role)
    await ctx.send(f"🎧 {member.mention} に「{SUB_GM_ROLE_NAME}」を付与しました。")

# ---------------------------------------------------------
# 機能1：GM設定
# ---------------------------------------------------------
@bot.command()
async def setgm(ctx, member: discord.Member):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=GM_ROLE_NAME)
    if not role:
        role = await guild.create_role(name=GM_ROLE_NAME, color=discord.Color.red(), hoist=True)

    for old_gm in role.members:
        if old_gm.id != member.id:
            try:
                await old_gm.remove_roles(role)
            except:
                pass
    
    await member.add_roles(role)
    await ctx.send(f"👑 {member.mention} をGMに設定しました！")

# ---------------------------------------------------------
# 機能2：会場セットアップ（広間をカテゴリ内へ移動）
# ---------------------------------------------------------
@bot.command()
async def setup(ctx, *char_names):
    if not char_names:
        await ctx.send("キャラクター名を入力してください")
        return

    guild = ctx.guild

    # 1. ロール確認
    gm_role = discord.utils.get(guild.roles, name=GM_ROLE_NAME)
    sub_gm_role = discord.utils.get(guild.roles, name=SUB_GM_ROLE_NAME)

    # 権限テンプレート
    # 【公開用】全員閲覧・接続可
    public_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, connect=True, view_channel=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, connect=True),
    }
    # 【非公開用】全員不可（GMのみ可）
    private_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False, view_channel=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, connect=True),
    }
    
    # GM権限追加
    if gm_role:
        public_overwrites[gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)
        private_overwrites[gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)
    if sub_gm_role:
        public_overwrites[sub_gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)
        private_overwrites[sub_gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)

    # 2. カテゴリー作成/取得
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME, overwrites=public_overwrites)
        await ctx.send(f"🏗️ カテゴリー「{CATEGORY_NAME}」を作成しました。")
    else:
        await ctx.send(f"🏗️ 既存のカテゴリー「{CATEGORY_NAME}」を使用します。")
        await category.set_permissions(guild.default_role, read_messages=True, connect=True, view_channel=True)

    # 3. 常設チャンネルの作成（広間もここに移動）

    # (A) 広間（Main Hall）★カテゴリ内に作成
    main_vc = discord.utils.get(category.voice_channels, name=MAIN_VC_NAME)
    if not main_vc:
        await guild.create_voice_channel(MAIN_VC_NAME, category=category, overwrites=public_overwrites)
    else:
        await main_vc.set_permissions(guild.default_role, view_channel=True, connect=True)

    # (B) GM控室（非公開）
    gm_channel = discord.utils.get(category.text_channels, name=GM_TEXT_CHANNEL_NAME)
    if not gm_channel:
        await guild.create_text_channel(GM_TEXT_CHANNEL_NAME, category=category, overwrites=private_overwrites)
    else:
        await gm_channel.set_permissions(guild.default_role, read_messages=False)

    # (C) 全体議論（公開）
    general_channel = discord.utils.get(category.text_channels, name=GENERAL_TEXT_CHANNEL_NAME)
    if not general_channel:
        await guild.create_text_channel(GENERAL_TEXT_CHANNEL_NAME, category=category, overwrites=public_overwrites)
    else:
        await general_channel.set_permissions(guild.default_role, read_messages=True, send_messages=True)

    # (D) 密談部屋（公開）
    for vc_name in SECRET_VC_NAMES:
        secret_vc = discord.utils.get(category.voice_channels, name=vc_name)
        if not secret_vc:
            await guild.create_voice_channel(vc_name, category=category, overwrites=public_overwrites)
        else:
            await secret_vc.set_permissions(guild.default_role, view_channel=True, connect=True)

    created_roles = []
    
    # 4. キャラクターごとの処理（非公開）
    for name in char_names:
        new_role = await guild.create_role(name=name, mentionable=True)
        created_roles.append(new_role)

        text_overwrites = private_overwrites.copy()
        text_overwrites[new_role] = discord.PermissionOverwrite(read_messages=True)

        await guild.create_text_channel(name, category=category, overwrites=text_overwrites)

    # 5. 公開チャンネルへの権限許可（念のため）
    targets = [general_channel]
    for vc_name in SECRET_VC_NAMES:
        targets.append(discord.utils.get(category.voice_channels, name=vc_name))
    targets.append(main_vc) # 広間も追加

    for channel in targets:
        if channel:
            for role in created_roles:
                # テキストならread/send, ボイスならconnect/view
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(role, read_messages=True, send_messages=True)
                else:
                    await channel.set_permissions(role, connect=True, view_channel=True)

    await ctx.send(
        f"✅ セットアップ完了！\n"
        f"「{MAIN_VC_NAME}」を含むすべての部屋をカテゴリー内に用意しました。\n"
        f"ロール: {', '.join([r.name for r in created_roles])}"
    )

# ---------------------------------------------------------
# 機能3：配役 (!cast) - エラー処理付き
# ---------------------------------------------------------
@bot.command()
async def cast(ctx, role_name: str, member: discord.Member):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=role_name)
    
    if not role:
        await ctx.send(f"⚠️ 役職「{role_name}」が見つかりません。")
        return

    try:
        await member.add_roles(role)
        target_channel = discord.utils.get(guild.text_channels, name=role_name, category=discord.utils.get(guild.categories, name=CATEGORY_NAME))
        link = target_channel.mention if target_channel else ""
        await ctx.send(f"🎭 {member.mention} を「{role.name}」に配役しました！ {link}")
    except Exception as e:
        await ctx.send(f"エラー: {e}")

@cast.error
async def cast_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ **入力が足りません**\n使い方: `!cast 役職名 @ユーザー名`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("⚠️ **ユーザーが見つかりません**\nメンションを確認してください。")

# ---------------------------------------------------------
# 機能4：タイマー (!timer) - 参加者メンション版
# ---------------------------------------------------------
@bot.command()
async def timer(ctx, minutes: int, *, memo="タイマー"):
    await ctx.send(f"⏳ **{memo}** を開始します！（{minutes}分間）")
    await asyncio.sleep(minutes * 60)
    
    # カテゴリー内の役職付きチャンネルを探してメンションを作成
    mentions = []
    category = discord.utils.get(ctx.guild.categories, name=CATEGORY_NAME)
    
    if category:
        # 除外するチャンネル名（システム用）
        ignore_channels = [GM_TEXT_CHANNEL_NAME, GENERAL_TEXT_CHANNEL_NAME]
        
        for channel in category.text_channels:
            if channel.name not in ignore_channels:
                # チャンネル名と同じロールを探す
                role = discord.utils.get(ctx.guild.roles, name=channel.name)
                if role:
                    mentions.append(role.mention)
    
    # メンションの文字列を作成（なければ空白）
    mention_str = " ".join(mentions) if mentions else ""
    
    await ctx.send(f"⏰ {mention_str} **{memo}** の {minutes}分が経過しました！")
# ---------------------------------------------------------
# 機能5：集合・移動 (!gather)
# ---------------------------------------------------------
@bot.command()
async def gather(ctx, minutes: int = 0):
    # 検索方法を変更：カテゴリ内の「広間」を探す
    category = discord.utils.get(ctx.guild.categories, name=CATEGORY_NAME)
    if category:
        main_vc = discord.utils.get(category.voice_channels, name=MAIN_VC_NAME)
    else:
        # カテゴリがない場合は全体から探す（フォールバック）
        main_vc = discord.utils.get(ctx.guild.voice_channels, name=MAIN_VC_NAME)

    if not main_vc:
        await ctx.send(f"エラー：「{MAIN_VC_NAME}」が見つかりません。")
        return

    if minutes > 0:
        await ctx.send(f"⏳ 密談終了の **{minutes}分後** に全員を「{MAIN_VC_NAME}」へ集合させます。")
        await asyncio.sleep(minutes * 60)
        await ctx.send("⏰ 時間です！プレイヤーを広間へ移動させます...")
    else:
        await ctx.send("📢 **全員集合！** 直ちにプレイヤーを広間へ移動させます...")

    count = 0
    if category:
        for channel in category.voice_channels:
            # 移動先と同じチャンネルにいる人は無視
            if channel.id == main_vc.id:
                continue

            for member in channel.members:
                if discord.utils.get(member.roles, name=GM_ROLE_NAME): continue
                if discord.utils.get(member.roles, name=SUB_GM_ROLE_NAME): continue
                if member.bot: continue

                try:
                    await member.move_to(main_vc)
                    count += 1
                except:
                    pass
    
    if count > 0:
        await ctx.send(f"🏃 {count}名を移動させました。")
    else:
        await ctx.send("（移動対象のプレイヤーはいませんでした）")

# ---------------------------------------------------------
# 機能6：お片付け (!cleanup)
# ---------------------------------------------------------
@bot.command()
async def cleanup(ctx):
    category = discord.utils.get(ctx.guild.categories, name=CATEGORY_NAME)
    if not category:
        await ctx.send("削除する会場が見つかりません。")
        return

    await ctx.send("🗑️ セッション終了処理を開始します...")

    # ★広間(MAIN_VC_NAME)も削除しないリストに追加
    keep_channels = [GM_TEXT_CHANNEL_NAME, GENERAL_TEXT_CHANNEL_NAME, MAIN_VC_NAME]
    keep_channels.extend(SECRET_VC_NAMES)

    roles_to_delete = []

    for channel in category.text_channels:
        if channel.name in keep_channels:
            continue
        for target in channel.overwrites:
            if isinstance(target, discord.Role):
                if target.name in [GM_ROLE_NAME, SUB_GM_ROLE_NAME]: continue
                if target.is_default(): continue
                if target.managed: continue
                if target not in roles_to_delete:
                    roles_to_delete.append(target)

    deleted_channels = 0
    for channel in category.channels:
        if channel.name not in keep_channels:
            await channel.delete()
            deleted_channels += 1

    deleted_roles = 0
    for role in roles_to_delete:
        try:
            await role.delete()
            deleted_roles += 1
        except:
            pass

    await ctx.send(f"✨ リセット完了！\n部屋 {deleted_channels}個 と、キャラクターロール {deleted_roles}個 を削除しました。")


bot.run(TOKEN)

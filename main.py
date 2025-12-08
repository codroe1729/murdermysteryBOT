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
SUB_GM_ROLE_NAME = "GMサブ"         # サブGMロール名
GM_TEXT_CHANNEL_NAME = "gm控室"     # GM専用ch（非公開）
GENERAL_TEXT_CHANNEL_NAME = "全体議論" # 全員用ch（公開）
SECRET_VC_NAMES = ["密談1", "密談2"]   # 密談用VC（公開）
# ==========================================

# ★現在実行中のタイマーを記憶する変数
current_timer_task = None

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
# 機能2：会場セットアップ
# ---------------------------------------------------------
@bot.command()
async def setup(ctx, *char_names):
    if not char_names:
        await ctx.send("キャラクター名を入力してください")
        return

    guild = ctx.guild
    gm_role = discord.utils.get(guild.roles, name=GM_ROLE_NAME)
    sub_gm_role = discord.utils.get(guild.roles, name=SUB_GM_ROLE_NAME)

    public_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, connect=True, view_channel=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, connect=True),
    }
    private_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False, view_channel=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, connect=True),
    }
    
    if gm_role:
        public_overwrites[gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)
        private_overwrites[gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)
    if sub_gm_role:
        public_overwrites[sub_gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)
        private_overwrites[sub_gm_role] = discord.PermissionOverwrite(read_messages=True, connect=True)

    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME, overwrites=public_overwrites)
        await ctx.send(f"🏗️ カテゴリー「{CATEGORY_NAME}」を作成しました。")
    else:
        await ctx.send(f"🏗️ 既存のカテゴリー「{CATEGORY_NAME}」を使用します。")
        await category.set_permissions(guild.default_role, read_messages=True, connect=True, view_channel=True)

    main_vc = discord.utils.get(category.voice_channels, name=MAIN_VC_NAME)
    if not main_vc:
        await guild.create_voice_channel(MAIN_VC_NAME, category=category, overwrites=public_overwrites)
    else:
        await main_vc.set_permissions(guild.default_role, view_channel=True, connect=True)

    gm_channel = discord.utils.get(category.text_channels, name=GM_TEXT_CHANNEL_NAME)
    if not gm_channel:
        await guild.create_text_channel(GM_TEXT_CHANNEL_NAME, category=category, overwrites=private_overwrites)
    else:
        await gm_channel.set_permissions(guild.default_role, read_messages=False)

    general_channel = discord.utils.get(category.text_channels, name=GENERAL_TEXT_CHANNEL_NAME)
    if not general_channel:
        await guild.create_text_channel(GENERAL_TEXT_CHANNEL_NAME, category=category, overwrites=public_overwrites)
    else:
        await general_channel.set_permissions(guild.default_role, read_messages=True, send_messages=True)

    for vc_name in SECRET_VC_NAMES:
        secret_vc = discord.utils.get(category.voice_channels, name=vc_name)
        if not secret_vc:
            await guild.create_voice_channel(vc_name, category=category, overwrites=public_overwrites)
        else:
            await secret_vc.set_permissions(guild.default_role, view_channel=True, connect=True)

    created_roles = []
    for name in char_names:
        new_role = await guild.create_role(name=name, mentionable=True)
        created_roles.append(new_role)
        text_overwrites = private_overwrites.copy()
        text_overwrites[new_role] = discord.PermissionOverwrite(read_messages=True)
        await guild.create_text_channel(name, category=category, overwrites=text_overwrites)

    targets = [general_channel]
    for vc_name in SECRET_VC_NAMES:
        targets.append(discord.utils.get(category.voice_channels, name=vc_name))
    targets.append(main_vc)

    for channel in targets:
        if channel:
            for role in created_roles:
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(role, read_messages=True, send_messages=True)
                else:
                    await channel.set_permissions(role, connect=True, view_channel=True)

    await ctx.send(f"✅ セットアップ完了！\nロール: {', '.join([r.name for r in created_roles])}")

# ---------------------------------------------------------
# 機能3：配役 (!cast)
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
# 機能4：タイマー (!timer) - 停止機能付き
# ---------------------------------------------------------
@bot.command()
async def timer(ctx, minutes: int, *, memo="タイマー"):
    global current_timer_task

    # 既に動いているタイマーがあればキャンセルする
    if current_timer_task is not None and not current_timer_task.done():
        current_timer_task.cancel()
        await ctx.send("⚠️ 前回のタイマーを停止して、新しいタイマーを開始します。")

    # 今回のコマンド（タスク）をグローバル変数に保存
    current_timer_task = asyncio.current_task()

    # メンション対象の特定
    mentions = []
    category = discord.utils.get(ctx.guild.categories, name=CATEGORY_NAME)
    if category:
        ignore_channels = [GM_TEXT_CHANNEL_NAME, GENERAL_TEXT_CHANNEL_NAME]
        for channel in category.text_channels:
            if channel.name not in ignore_channels:
                role = discord.utils.get(ctx.guild.roles, name=channel.name)
                if role:
                    mentions.append(role.mention)
    mention_str = " ".join(mentions) if mentions else ""

    try:
        await ctx.send(f"⏳ **{memo}** を開始します！（{minutes}分間）")
        
        total_seconds = minutes * 60
        remaining = total_seconds

        # 4分以上なら「半分」で通知
        if minutes >= 4:
            half_seconds = total_seconds / 2
            await asyncio.sleep(half_seconds)
            remaining -= half_seconds
            await ctx.send(f"🔔 {mention_str} **{memo}** 残り {minutes/2}分（折り返し）です！")
            
            await asyncio.sleep(remaining - 60)
            remaining = 60
            await ctx.send(f"⚠️ {mention_str} **{memo}** 残り 1分です！")

        # 2分以上なら「残り1分」で通知
        elif minutes >= 2:
            await asyncio.sleep(remaining - 60)
            remaining = 60
            await ctx.send(f"⚠️ {mention_str} **{memo}** 残り 1分です！")

        # 最後の待機
        if remaining > 0:
            await asyncio.sleep(remaining)

        await ctx.send(f"⏰ {mention_str} **{memo}** 終了！ ({minutes}分経過)")

    except asyncio.CancelledError:
        # !stop でキャンセルされた時にここを通る
        await ctx.send(f"🛑 **{memo}** を強制停止しました。")
    finally:
        current_timer_task = None

# ---------------------------------------------------------
# 機能4-B：タイマー停止 (!stop) ★追加
# ---------------------------------------------------------
@bot.command()
async def stop(ctx):
    global current_timer_task
    if current_timer_task and not current_timer_task.done():
        current_timer_task.cancel() # タイマー処理に「キャンセル」シグナルを送る
        # メッセージは !timer 側の except ブロックで表示されます
    else:
        await ctx.send("現在動いているタイマーはありません。")

# ---------------------------------------------------------
# 機能5：集合・移動 (!gather) - 行き先指定＆自動帰還 対応版
# ---------------------------------------------------------
@bot.command()
async def gather(ctx, target_roles: commands.Greedy[discord.Role], minutes: int, dest_name: str = "密談1"):
    # ★タイマー管理
    global current_timer_task
    if current_timer_task is not None and not current_timer_task.done():
        current_timer_task.cancel()
        await ctx.send("⚠️ 前回のタイマーを停止して、新しい移動タイマーを開始します。")
    current_timer_task = asyncio.current_task()

    category = discord.utils.get(ctx.guild.categories, name=CATEGORY_NAME)
    
    # ---------------------------------------------------------
    # モード判定と移動先の決定
    # ---------------------------------------------------------
    dest_vc = None
    auto_return = False
    mode_str = ""
    targets = []

    # A. 役職指定あり（呼び出しモード）
    if target_roles:
        mode_str = "密談呼び出し"
        auto_return = True  # 自動で戻す
        
        # 指定された行き先（デフォルトは密談1）を探す
        if category:
            dest_vc = discord.utils.get(category.voice_channels, name=dest_name)
        else:
            dest_vc = discord.utils.get(ctx.guild.voice_channels, name=dest_name)
        
        if not dest_vc:
            await ctx.send(f"⚠️ エラー：移動先のチャンネル「{dest_name}」が見つかりません。")
            current_timer_task = None
            return

        # 対象メンバーの特定
        for role in target_roles:
            for member in role.members:
                if member.voice and member.voice.channel:
                    # 既にその部屋にいる人は移動不要
                    if member.voice.channel.id == dest_vc.id:
                        continue
                    targets.append(member)

    # B. 役職指定なし（全員集合モード）
    else:
        mode_str = "全員集合"
        auto_return = False # 戻さない
        
        # 行き先は必ず「広間」
        if category:
            dest_vc = discord.utils.get(category.voice_channels, name=MAIN_VC_NAME)
        else:
            dest_vc = discord.utils.get(ctx.guild.voice_channels, name=MAIN_VC_NAME)
            
        if not dest_vc:
            await ctx.send(f"エラー：「{MAIN_VC_NAME}」が見つかりません。")
            current_timer_task = None
            return

        # 対象メンバー（GM以外全員）
        if category:
            for channel in category.voice_channels:
                if channel.id == dest_vc.id: continue
                for member in channel.members:
                    if discord.utils.get(member.roles, name=GM_ROLE_NAME): continue
                    if discord.utils.get(member.roles, name=SUB_GM_ROLE_NAME): continue
                    if member.bot: continue
                    targets.append(member)

    # 重複排除
    targets = list(set(targets))
    moved_members = {} # 元の場所を記録

    if not targets:
        await ctx.send("移動対象のプレイヤーが見つかりませんでした。")
        current_timer_task = None
        return

    # ---------------------------------------------------------
    # 移動実行
    # ---------------------------------------------------------
    count = 0
    for member in targets:
        try:
            if auto_return:
                moved_members[member] = member.voice.channel
            await member.move_to(dest_vc)
            count += 1
        except:
            pass

    # 開始メッセージ
    role_mentions = " ".join([r.mention for r in target_roles]) if target_roles else "全員"
    await ctx.send(f"🏃 **{mode_str}**：{role_mentions} を「{dest_vc.name}」へ移動させました。（{count}名）")
    
    if auto_return:
        await ctx.send(f"⏳ **{minutes}分後** に元の場所へ戻します。")
    else:
        await ctx.send(f"⏳ **{minutes}分** の議論を開始します。")

    try:
        # ---------------------------------------------------------
        # タイマー待機処理
        # ---------------------------------------------------------
        if minutes > 0:
            total_seconds = minutes * 60
            
            # 残り1分通知（2分以上の場合のみ）
            if minutes >= 2:
                await asyncio.sleep(total_seconds - 60)
                
                # 通知用メンション作成
                mentions = []
                if target_roles:
                    # 指定呼び出しならそのロールにメンション
                    mentions = [r.mention for r in target_roles]
                else:
                    # 全員集合なら、今移動先にいるゲーム参加者にメンション
                    ignore_channels = [GM_TEXT_CHANNEL_NAME, GENERAL_TEXT_CHANNEL_NAME]
                    game_role_names = []
                    if category:
                        game_role_names = [c.name for c in category.text_channels if c.name not in ignore_channels]
                    
                    for member in dest_vc.members:
                        for role in member.roles:
                            if role.name in game_role_names:
                                mentions.append(role.mention)
                
                mention_str = " ".join(list(set(mentions)))
                if mention_str:
                    await ctx.send(f"⚠️ {mention_str} 時間終了まで残り 1分です！")
                
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(total_seconds)

            # ---------------------------------------------------------
            # 終了処理（自動帰還）
            # ---------------------------------------------------------
            await ctx.send("⏰ 時間です！")

            if auto_return and moved_members:
                await ctx.send("↩️ プレイヤーを元の場所へ戻します...")
                return_count = 0
                for member, original_channel in moved_members.items():
                    try:
                        if member.voice:
                            await member.move_to(original_channel)
                            return_count += 1
                    except:
                        pass
                await ctx.send(f"✨ {return_count}名を元の部屋へ戻しました。")
            
            elif not auto_return:
                await ctx.send("（全員集合モードのため、自動では戻りません）")

    except asyncio.CancelledError:
        await ctx.send(f"🛑 {mode_str}タイマーを停止しました。（自動移動はキャンセルされます）")
    finally:
        current_timer_task = None

# ---------------------------------------------------------
# 機能6：お片付け (!cleanup) - ログ削除機能付き
# ---------------------------------------------------------
@bot.command()
async def cleanup(ctx):
    category = discord.utils.get(ctx.guild.categories, name=CATEGORY_NAME)
    if not category:
        await ctx.send("削除する会場が見つかりません。")
        return

    await ctx.send("🗑️ セッション終了処理を開始します...")

    # 1. ログを削除したいチャンネルの名前リスト
    # GM控室、全体議論、広間(VCのチャット) を対象にする
    log_purge_targets = [GM_TEXT_CHANNEL_NAME, GENERAL_TEXT_CHANNEL_NAME, MAIN_VC_NAME]

    keep_channels = [GM_TEXT_CHANNEL_NAME, GENERAL_TEXT_CHANNEL_NAME, MAIN_VC_NAME]
    keep_channels.extend(SECRET_VC_NAMES)

    roles_to_delete = []

    # テキストチャンネルの処理（削除 or ログ消去）
    for channel in category.text_channels:
        # 常設チャンネルの場合：削除せず、ログだけ消す
        if channel.name in log_purge_targets:
            try:
                # 履歴を全消去 (limit=Noneで全て)
                await channel.purge(limit=None)
                # 完了メッセージを(消した後に)一瞬だけ出す
                await channel.send("🧹 ログを全消去しました。", delete_after=5)
            except Exception as e:
                print(f"ログ削除エラー({channel.name}): {e}")
            continue # チャンネル自体は消さないのでスキップ

        # その他のチャンネル（キャラ部屋）は削除対象のロールを探して記録
        if channel.name in keep_channels:
            continue
            
        for target in channel.overwrites:
            if isinstance(target, discord.Role):
                if target.name in [GM_ROLE_NAME, SUB_GM_ROLE_NAME]: continue
                if target.is_default(): continue
                if target.managed: continue
                if target not in roles_to_delete:
                    roles_to_delete.append(target)

    # ボイスチャンネルの処理（削除 or ログ消去）
    for channel in category.voice_channels:
        # 広間(VC)のテキストチャットも消去する
        if channel.name in log_purge_targets:
            try:
                await channel.purge(limit=None)
            except:
                pass # VCにテキストがない場合などは無視
        
        if channel.name not in keep_channels:
            await channel.delete()

    # キャラ部屋（テキスト）の削除
    deleted_channels = 0
    for channel in category.text_channels:
        if channel.name not in keep_channels:
            await channel.delete()
            deleted_channels += 1

    # ロールの削除
    deleted_roles = 0
    for role in roles_to_delete:
        try:
            await role.delete()
            deleted_roles += 1
        except:
            pass

    # 実行元のチャンネルが消えていなければ完了報告
    try:
        await ctx.send(f"✨ リセット完了！\n・常設部屋のログを全消去しました。\n・キャラクター部屋 {deleted_channels}個 とロール {deleted_roles}個 を削除しました。")
    except:
        pass # もし自分(GM控室)のログを消してしまってメッセージが送れない場合は無視

bot.run(TOKEN)

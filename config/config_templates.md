# 設定ファイルテンプレート

各種設定ファイルのテンプレートと説明です。以下のファイルを`config/`ディレクトリに作成してください。

## 1. LLM設定 (`config/llm_config.yaml`)

```yaml
# LLM API設定
llm:
  # 主要プロバイダー
  primary_provider: "openai"  # openai/anthropic/google
  
  # OpenAI設定
  openai:
    model: "gpt-4"
    temperature: 0.7
    max_tokens: 2000
    timeout: 30
    retry_attempts: 3
    
  # Anthropic Claude設定
  anthropic:
    model: "claude-3-sonnet-20240229"
    temperature: 0.7
    max_tokens: 2000
    timeout: 30
    
  # プロンプト設定
  prompts:
    theme_generation: |
      以下の条件で動画テーマを生成してください：
      - ターゲット: {target_audience}
      - ジャンル: {preferred_genres}
      - 除外ジャンル: {excluded_genres}
      - 動画尺: {duration}分
      
    script_generation: |
      以下のテーマで{speaker_count}人の{tone}な雑談動画スクリプトを生成：
      テーマ: {theme}
      動画尺: {duration}分
      話者: {speakers}
```

## 2. 音声合成設定 (`config/voice_config.yaml`)

```yaml
# TTS設定
tts:
  # 主要プロバイダー
  primary_provider: "aivis"  # aivis/azure/google
  
  # AIVIS Speech設定
  aivis:
    timeout: 60
    retry_attempts: 3
    voice_presets:
      reimu:
        voice_id: "reimu_voice_001"
        speed: 1.0
        pitch: 0.0
        emotion: "normal"
      marisa:
        voice_id: "marisa_voice_001"
        speed: 1.1
        pitch: -0.1
        emotion: "cheerful"
        
  # Azure Speech設定
  azure:
    voice_name: "ja-JP-NanamiNeural"
    speaking_rate: "1.0"
    pitch: "+0Hz"
    
  # 音声後処理設定
  audio_processing:
    sample_rate: 44100
    channels: 2
    normalize_volume: true
    target_lufs: -23.0
    fade_in_ms: 100
    fade_out_ms: 200
```

## 3. キャラクター設定 (`config/character_config.yaml`)

```yaml
# 立ち絵・キャラクター設定
characters:
  # 立ち絵使用設定
  enabled: true
  
  # キャラクター定義
  available_characters:
    reimu:
      name: "博麗霊夢"
      sprite_path: "assets/characters/reimu/"
      expressions:
        - "normal"
        - "happy"
        - "angry"
        - "surprised"
      mouth_sprites:
        open: "mouth_open.png"
        closed: "mouth_closed.png"
      position:
        x: 100
        y: 200
        scale: 1.0
        
    marisa:
      name: "霧雨魔理沙"
      sprite_path: "assets/characters/marisa/"
      expressions:
        - "normal"
        - "happy"
        - "smug"
        - "thinking"
      mouth_sprites:
        open: "mouth_open.png"
        closed: "mouth_closed.png"
      position:
        x: 700
        y: 200
        scale: 1.0
        
  # アニメーション設定
  animation:
    frame_rate: 30
    mouth_sync_enabled: true
    expression_change_threshold: 0.5  # 感情値の閾値
    
  # 出力設定
  output:
    resolution: [1920, 1080]
    background_alpha: 0  # 透明背景
    video_codec: "libx264"
    pixel_format: "yuva420p"
```

## 4. 字幕設定 (`config/subtitle_config.yaml`)

```yaml
# 字幕設定
subtitles:
  # フォント設定
  font:
    family: "Noto Sans CJK JP"
    size: 48
    bold: true
    italic: false
    
  # スタイル設定
  style:
    primary_color: "#FFFFFF"  # 白
    secondary_color: "#000000"  # 黒（縁取り）
    outline_width: 3
    shadow_offset: [2, 2]
    shadow_color: "#808080"
    
  # 位置設定
  position:
    alignment: "bottom_center"
    margin_bottom: 80
    margin_left: 50
    margin_right: 50
    
  # タイミング設定
  timing:
    min_duration: 1.0  # 最小表示時間（秒）
    max_line_length: 30  # 1行の最大文字数
    line_break_threshold: 20  # 改行する文字数
    
  # 強調表示
  emphasis:
    enabled: true
    keywords: ["重要", "注意", "ポイント"]
    color: "#FF6B6B"  # 赤色
    
  # エフェクト
  effects:
    fade_in_duration: 0.3
    fade_out_duration: 0.3
    typewriter_effect: false
```

## 5. 動画エンコード設定 (`config/encoding_config.yaml`)

```yaml
# 動画エンコード設定
encoding:
  # プリセット定義
  presets:
    # YouTube用横動画
    youtube_landscape:
      resolution: [1920, 1080]
      frame_rate: 30
      video_codec: "libx264"
      video_bitrate: "8M"
      audio_codec: "aac"
      audio_bitrate: "320k"
      pixel_format: "yuv420p"
      
    # YouTube用縦動画
    youtube_portrait:
      resolution: [1080, 1920]
      frame_rate: 60
      video_codec: "libx264"
      video_bitrate: "10M"
      audio_codec: "aac"
      audio_bitrate: "320k"
      pixel_format: "yuv420p"
      
    # 高品質版
    high_quality:
      resolution: [1920, 1080]
      frame_rate: 60
      video_codec: "libx264"
      video_bitrate: "15M"
      audio_codec: "aac"
      audio_bitrate: "320k"
      pixel_format: "yuv420p"
      
  # デフォルト設定
  default_preset: "youtube_landscape"
  
  # FFmpeg設定
  ffmpeg:
    threads: 0  # 自動
    preset: "medium"  # ultrafast/superfast/veryfast/faster/fast/medium/slow/slower/veryslow
    crf: 18  # 品質（低いほど高品質）
    
  # エラー処理
  error_handling:
    max_retries: 3
    retry_delay: 5
    fallback_preset: "youtube_landscape"
```

## 6. YouTube投稿設定 (`config/youtube_config.yaml`)

```yaml
# YouTube API設定
youtube:
  # アップロード設定
  upload:
    privacy_status: "private"  # private/unlisted/public
    category_id: "22"  # People & Blogs
    default_language: "ja"
    
  # メタデータテンプレート
  metadata:
    title_template: "{title}"
    description_template: |
      {description}
      
      #ゆっくり解説 #東方 #{tags}
      
      【注意事項】
      この動画は東方Projectの二次創作です。
      東方Project © 上海アリス幻樂団
      
    tags:
      default: ["ゆっくり解説", "東方", "霊夢", "魔理沙"]
      max_count: 15
      
  # サムネイル設定
  thumbnail:
    auto_generate: true
    template_path: "assets/templates/thumbnail_template.png"
    
  # 公開設定
  scheduling:
    auto_publish: false
    publish_delay_hours: 0
    optimal_time: "20:00"  # JST
    
  # 制限設定
  limits:
    max_uploads_per_day: 5
    max_file_size_gb: 2
    check_quotas: true
```

## 7. 設定ファイルの作成方法

### 7.1 一括作成スクリプト

以下のコマンドで設定ファイルのテンプレートを一括作成：

```bash
# 設定ディレクトリ作成
mkdir -p config

# 各設定ファイルを作成（上記の内容をコピー）
touch config/llm_config.yaml
touch config/voice_config.yaml
touch config/character_config.yaml
touch config/subtitle_config.yaml
touch config/encoding_config.yaml
touch config/youtube_config.yaml
```

### 7.2 設定ファイルの検証

設定ファイルが正しく作成されているか確認：

```bash
# 設定ファイルの構文チェック
python -m yaml -c config/llm_config.yaml
python -m yaml -c config/voice_config.yaml
# ... 他の設定ファイルも同様に
```

### 7.3 設定のカスタマイズ

1. **開発環境**: デバッグ用の設定を有効化
2. **本番環境**: 品質とパフォーマンスを最適化
3. **テスト環境**: モック使用とログ詳細化

各環境に応じて設定値を調整してください。 
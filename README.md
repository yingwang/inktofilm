<p align="center">
  <img src="docs/assets/vidspec-mark.svg" width="112" alt="InkToFilm mark">
</p>

<h1 align="center">InkToFilm</h1>

<p align="center">
  <strong>One prompt in. A finished film out.</strong><br>
  No code. No command line. Just tell Claude Code or Codex what you want to watch.
</p>

<p align="center">
  English · <a href="#inktofilm-中文说明">中文说明</a>
</p>

<p align="center">
  <a href="https://github.com/yingwang/inktofilm/actions/workflows/ci.yml"><img src="https://github.com/yingwang/inktofilm/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-5ee6d0" alt="MIT License"></a>
</p>

<p align="center">
  <a href="examples/great-havoc-in-heaven/great-havoc-in-heaven-trailer.mp4">
    <img src="docs/assets/great-havoc-in-heaven/trailer-contact-sheet.jpg" width="100%" alt="Six scenes from the InkToFilm Great Havoc in Heaven trailer">
  </a>
</p>

<p align="center">
  <a href="examples/great-havoc-in-heaven/great-havoc-in-heaven-trailer.mp4"><strong>▶ Watch the finished 30-second film</strong></a>
</p>

## Say what you want to make

The [InkToFilm skill](skills/inktofilm/SKILL.md) works in both Claude Code and Codex. Claude Code
discovers it automatically through `.claude/skills` when you open this repository; to have it in
every project, link it once with
`ln -s "$PWD/skills/inktofilm" ~/.claude/skills/inktofilm` and invoke it as `/inktofilm`. In Codex,
ask it to install the skill and invoke it as `$inktofilm`. Either way, describe your film in
ordinary language:

> Use the InkToFilm skill to make a 30-second IMAX-style trailer where the Monkey King challenges
> all of Heaven. Live action, monumental scale, no comedy.

Or bring more detail:

> Use the InkToFilm skill to turn my screenplay into a cinematic short. Keep the heroine's face and
> costume consistent, preserve every line of dialogue, and make the ending quiet rather than
> melodramatic.

Or start a series:

> Use the InkToFilm skill to create a three-scene fantasy pilot from this premise. First make a
> 45-second proof of concept, then keep the same cast and world bible for the next scene.

That is the interface. InkToFilm develops the script, plans the shots, generates the footage, checks
whether the story is actually visible, fixes weak takes, edits the selected clips, and returns a
playable film.

When generation is about to begin, the skill asks for a fal API key only if one is not already
available. It keeps the key local and private, shows the spending cap before paid requests, and never
places credentials in the film project or Git history.

## From an idea to a film

<p align="center">
  <img src="docs/assets/production-pipeline.svg" width="100%" alt="A prompt becomes a screenplay, storyboard, generated footage, reviewed shots, and a finished film">
</p>

You give InkToFilm one sentence or a complete screenplay. It handles the rest:

- writes a shootable story and keeps a character and world bible;
- renders a reference portrait for each character, then locks each shot's opening frame as a still
  before spending a video credit on it;
- turns the story into cinematic shots with continuity anchors, written the way a cinematographer
  briefs a crew: the medium and the physics first, every action on a clock, and text-to-video for
  wide action so the model owns the motion instead of animating a photograph;
- generates every scene with the video model you choose;
- reviews story fidelity, action, composition, anatomy, text, black frames, freezes, and the tempo
  of action takes;
- retries only the shots that meaningfully failed;
- edits the approved footage, sound, and title cards into one film.

### Stills, faces, and shots that join up

Three of those steps deserve naming, because they are what keep a face and a costume alive across a
whole film rather than for five seconds at a time.

**A still first.** Framing, costume, and light are cheap to fix in an image and expensive to fix in
a clip. Each character gets one clean reference portrait, every shot's still is edited from those
portraits, and the shot is then generated from its own still. One face and one costume carry the
whole film.

**A real face, where it can survive.** Point `--face traveler=photo.jpg` at a character and that
photographed face is put onto their portrait and onto their close-up stills. Two people in one frame
each get their own face: a two-face model takes both in one request, and a single-face model is
applied strip by strip so it cannot replace the wrong person. The planner marks only the shots framed
tightly enough to hold a face: on a wide shot it covers too few pixels to swap cleanly, and the
attempt reads as a deformed face rather than a likeness. The photo is uploaded to the swap model and
never written into any text prompt.

**Cuts that actually join.** Where the action runs straight on with no cut, the next shot's still is
handed to the video model as this shot's mandated last frame. The two clips then meet on the same
image instead of merely resembling each other, and a re-shoot of one segment drops back in without
disturbing its neighbours.

**Or continue from the take itself.** When several shots share one unbroken stretch of time, a shot
can open on a frame cut from the previous shot's finished clip, a fraction of a second before its
end or at any offset you name. The same people, costumes, light and place carry across without a
still of their own, the photographed faces are put back onto the handoff frame where they are large
enough to hold, and choosing a different take upstream refreshes every frame that follows it.

**Tempo you can read.** An action take is measured as well as watched: InkToFilm charts the
frame-to-frame motion of a clip per half second, so a fight that floats instead of fighting, or a
shot that never moves, is caught before it reaches the edit.

## Demo 1 · *Journey to the West: Great Havoc in Heaven*

The prompt was simple: make a theatrical, live-action *Journey to the West* trailer with blockbuster
scale. InkToFilm wrote a five-shot plan, generated the footage with MiniMax H3 Max, repaired the weak
climax, continued one directly connected action from a selected stable frame, connected the other
shots with lightning and sound bridges, mixed a three-line Mandarin dialogue arc that carries across
two cuts, and typeset the title card locally so the film's only text is exact and reproducible.

<p align="center">
  <a href="examples/great-havoc-in-heaven/great-havoc-in-heaven-trailer.mp4">
    <img src="docs/assets/great-havoc-in-heaven/trailer-hero.jpg" width="100%" alt="The South Heavenly Gate collapsing in the Great Havoc in Heaven trailer">
  </a>
</p>

- Finished film: **30 seconds**, **1344×768**, **24 fps**, stereo audio.
- Quality result: **5 of 5 scenes passed** and **25 of 25 story assertions passed**.
- Generation cost for the selected shots and targeted retries: **$2.00 on fal**; the three spoken
  lines cost less than **$0.10**.
- Public materials: [screenplay](examples/great-havoc-in-heaven/script.md),
  [shot prompts](examples/great-havoc-in-heaven/prompts.md), and
  [evidence-backed review](examples/great-havoc-in-heaven/report/index.html). The edit, the spoken
  lines, and the title card are reproduced by the scripts in
  [`scripts/`](scripts/).

## Demo 2 · It fixes weak takes instead of hiding them

The first climax had a strong explosion but an indistinct hero and unstable weapon. A targeted retry
fixed the character while preserving the best impact beat. InkToFilm selected and edited the useful
moments into the final shot.

<p align="center">
  <img src="docs/assets/great-havoc-in-heaven/shot-05-before-after.jpg" width="100%" alt="Before and after frame sequences from the South Heavenly Gate climax">
</p>

The final review scored the gate impact **0.91**, layered destruction **0.87**, the full-body Monkey
King **0.96**, character and weapon stability **0.94**, and clean overlays **1.00**.

## Demo 3 · It checks whether the story happened

This separate MiniMax shot asks for Sun Wukong to land beside Tang Sanzang and a white horse, point
toward a thundercloud, and hold all three identities through one camera move.

<p align="center">
  <a href="examples/journey-to-the-west/minimax-h3.mp4">
    <img src="docs/assets/journey-to-the-west/contact-sheet.jpg" width="100%" alt="Five frames from a Journey to the West action-continuity example">
  </a>
</p>

<p align="center">
  <a href="examples/journey-to-the-west/minimax-h3.mp4">▶ Watch the generated scene</a>
  ·
  <a href="examples/journey-to-the-west/semantic-results.json">See the reviewed evidence</a>
</p>

InkToFilm does not reduce this to one mysterious score. It checks the cast, action order, setting,
identity continuity, camera intent, and unwanted text separately, with visible frame evidence for
each decision.

<p align="center">
  <img src="docs/assets/journey-to-the-west/semantic-report.png" width="100%" alt="InkToFilm story review with scored assertions and cited frame evidence">
</p>

## What you need

- **Claude Code or Codex**, for story development, shot planning, visual review, and the no-code
  conversation.
- **A fal API key**, for MiniMax video generation. InkToFilm can use another video provider when you
  choose one.

The skill handles installation and setup on your behalf. You never need to type a shell command to
make a film.

## What works today

InkToFilm can make complete short films, trailers, and proof-of-concept scenes from one prompt or a
screenplay. Feature films and television episodes are produced scene by scene with a shared cast and
world bible, then assembled from approved scenes.

Video models can still drift in faces, hands, dialogue, or motion. InkToFilm makes those failures
visible and retries them selectively; it does not pretend the underlying models are perfect.

## For builders

The conversational skill is the front door. The engine beneath it remains open and provider-neutral:
`inktofilm produce` runs a plan stage by stage (`--plan-only`, `--stills-only`, `--reshoot`,
`--select`), `inktofilm frames` and `inktofilm motion` give a reviewer the sampled frames and the
motion curve of any take, and `inktofilm run` replays a suite of story assertions against finished
clips. See the [technical guide](docs/technical-guide.md),
[provider protocols](docs/provider-protocols.md),
[semantic evaluator protocol](docs/semantic-evaluators.md), and
[research design](docs/research-design.md). Contributions are welcome through
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)

---

<h1 align="center" id="inktofilm-中文说明">InkToFilm 中文说明</h1>

<p align="center">
  <strong>一句话进去，一部成片出来。</strong><br>
  不写代码，不敲命令行，把想看的东西告诉 Claude Code 或 Codex 就可以。
</p>

<p align="center">
  <a href="#inktofilm">English</a> · 中文说明
</p>

## 说出你想拍什么

[InkToFilm skill](skills/inktofilm/SKILL.md) 同时支持 Claude Code 与 Codex。打开这个仓库时，Claude Code
会通过 `.claude/skills` 自动发现它；想在所有项目里都能用，执行一次
`ln -s "$PWD/skills/inktofilm" ~/.claude/skills/inktofilm`，之后用 `/inktofilm` 调用。在 Codex 里让它安装这个
skill，然后用 `$inktofilm` 调用。无论哪一种，用平常说话的方式描述你的片子就行：

> 用 InkToFilm skill 做一支三十秒的 IMAX 风格预告片，孙悟空单挑整个天庭。真人电影感，宏大的体量，不要喜剧。

也可以给得更细：

> 用 InkToFilm skill 把我的剧本做成一部电影感短片。女主角的脸和服装全程一致，每一句台词都保留，结尾要安静而不是煽情。

或者开一个系列：

> 用 InkToFilm skill 根据这个设定做一部三场戏的奇幻试播集。先做一个四十五秒的概念验证，之后沿用同一套演员与世界设定继续拍下一场。

这就是全部的使用方式。InkToFilm 负责发展剧本、规划镜头、生成素材、检查故事是否真的被拍出来了、修补弱镜头、剪辑选定的片段，最后交给你一部可以直接播放的片子。

生成开始前，如果环境里还没有 fal 的 API key，skill 才会向你要一次。key 只留在本地，付费请求之前会先告诉你花费上限，任何情况下都不会把凭据写进片子的项目目录或 Git 历史。

## 从一个想法到一部片子

<p align="center">
  <img src="docs/assets/production-pipeline.svg" width="100%" alt="一句话变成剧本、分镜、生成素材、审过的镜头与成片">
</p>

你给 InkToFilm 一句话，或者一个完整剧本，其余的它来做：

- 写出可拍的故事，维护一份人物与世界设定；
- 为每个角色画一张参考定妆照，再把每一镜的起始画面先锁成静帧，然后才花视频额度去拍；
- 把故事拆成带连续性锚点的电影镜头，提示词按摄影师给剧组交底的方式写：先说媒介与物理，再给每个动作一个时间点，远景与打戏用纯文字生成，让模型自己掌握运动，而不是让一张照片动起来；
- 用你选择的视频模型生成每一场；
- 逐镜审查故事还原度、动作、构图、人体结构、文字、黑帧、卡帧，以及动作镜头的节奏；
- 只重拍真正出问题的镜头；
- 把通过的素材、声音和片名字卡剪成一部完整的片子。

### 静帧、真脸与接得上的镜头

其中三件事值得单独说明，因为它们决定了一张脸和一套服装能不能贯穿整部片子，而不是只撑五秒。

**先有静帧。** 构图、服装、光线在图片里改起来便宜，在视频里改起来昂贵。每个角色先有一张干净的参考定妆照，每一镜的静帧都从定妆照改出来，镜头再从自己的静帧起动。于是一张脸、一套衣服可以贯穿全片。

**真脸只用在它能站住的地方。** 用 `--face traveler=photo.jpg` 给一个角色指定一张照片，这张脸会被换到该角色的定妆照和近景静帧上。同一画面里有两个人时，各换各的脸：双脸模型一次处理两张，单脸模型则按画面左右分条带分别处理，不会换错人。规划时只有景别足够近的镜头才会标记换脸：远景里一张脸只占很少的像素，换脸后只会得到一张变形的脸，而不是相像的脸。照片只上传给换脸模型，永远不会写进任何文字提示。

**真正接上的剪辑。** 动作直接延续、中间没有剪切时，下一镜的静帧会作为这一镜必须落到的最后一帧交给视频模型。两段素材于是在同一张画面上相接，而不是仅仅长得相似；重拍其中一段也不会牵动邻镜。

**或者直接从上一条素材接着拍。** 几个镜头处在同一段连续的时间里时，一个镜头可以直接以上一镜成片中的某一帧开场，取末尾前零点几秒，或者你指定的任何位置。同样的人物、服装、光线和地点由此延续下去，不需要自己的静帧；照片里的脸会在交接帧上脸够大的地方重新换上；上游换了一条素材，下游的每一帧也会随之刷新。

**看得见的节奏。** 动作镜头不只靠眼睛看，也靠测量：InkToFilm 会按每半秒统计一段素材逐帧的运动量并画成曲线，一场飘着不打的打戏，或者一镜根本没动的画面，在进入剪辑之前就会被发现。

## 示例一 · 《西游记：大闹天宫》

提示词很简单：做一支剧场级、真人电影质感、有大片体量的《西游记》预告片。InkToFilm 写了五镜的分镜计划，用 MiniMax H3 Max 生成素材，修补了偏弱的高潮镜头，把一段直接相连的动作从选定的稳定帧接着拍下去，其余镜头用闪电和声音桥接，混入一段跨越两处剪切的三句普通话对白，片名字卡在本地排版，使全片唯一的文字准确且可复现。

- 成片 **三十秒**，**1344×768**，**24 fps**，立体声。
- 质量结果：**五场全部通过**，**二十五条故事断言全部通过**。
- 选定镜头与定向重拍的生成费用：fal 上 **2.00 美元**；三句台词的花费不到 **0.10 美元**。
- 公开材料：[剧本](examples/great-havoc-in-heaven/script.md)、[镜头提示词](examples/great-havoc-in-heaven/prompts.md)、[带证据的审查报告](examples/great-havoc-in-heaven/report/index.html)。剪辑、台词与片名字卡由 [`scripts/`](scripts/) 里的脚本复现。

## 示例二 · 它修补弱镜头，而不是遮掩

第一版高潮有一场漂亮的爆炸，但主角模糊、武器不稳。一次定向重拍修好了角色，同时保留了最好的撞击瞬间。InkToFilm 把有用的部分挑出来，剪成最终镜头。

最终审查中，天门撞击得分 **0.91**，层次化的破坏 **0.87**，全身可见的孙悟空 **0.96**，角色与武器稳定性 **0.94**，无多余叠加文字 **1.00**。

## 示例三 · 它检查故事是否真的发生了

另一段 MiniMax 镜头要求孙悟空落在唐三藏与白马身边、指向一团雷云，并在一个运镜里保持三个人物的身份一致。InkToFilm 不会把这些压成一个神秘的分数，而是分别检查人物、动作顺序、场景、身份连续性、运镜意图和多余文字，每一项判断都附有可见的帧证据。见 [生成的场景](examples/journey-to-the-west/minimax-h3.mp4) 与 [审查证据](examples/journey-to-the-west/semantic-results.json)。

## 你需要什么

- **Claude Code 或 Codex**，负责剧本发展、镜头规划、视觉审查，以及整个无代码的对话过程。
- **一个 fal API key**，用于 MiniMax 视频生成。你也可以选择别的视频提供方。

安装与配置由 skill 代劳。做一部片子，你不需要敲任何一条 shell 命令。

## 现在能做到什么

InkToFilm 可以从一句话或一个剧本出发，做出完整的短片、预告片和概念验证场景。电影长片与剧集按场次逐场制作，共享同一套人物与世界设定，最后由通过审查的场次组装而成。

视频模型在脸、手、对白和运动上仍会漂移。InkToFilm 让这些失败可见，并有选择地重拍；它不会假装底层模型是完美的。

## 给开发者

对话式的 skill 是正门，底下的引擎保持开放且不绑定任何提供方：`inktofilm produce` 可以分阶段执行一份分镜计划（`--plan-only`、`--stills-only`、`--reshoot`、`--select`），`inktofilm frames` 与 `inktofilm motion` 分别给出任意一条素材的抽样帧和运动曲线，`inktofilm run` 则把一组故事断言回放到成片上。详见[技术指南](docs/technical-guide.md)、[提供方协议](docs/provider-protocols.md)、[语义评审协议](docs/semantic-evaluators.md)与[研究设计](docs/research-design.md)。欢迎通过 [CONTRIBUTING.md](CONTRIBUTING.md) 参与贡献。

## 许可

[MIT](LICENSE)

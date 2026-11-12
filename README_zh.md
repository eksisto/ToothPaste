
> 要是能把这串超长的密码复制到这台来路不明的电脑上,世界和平早就实现了。唉!看来只好手动输入了……
>
>\- 某个肯定说过这话的人

<div align="center">
  <h1 style="text-align: center; margin: 10;">
    <span style="display: inline-flex; align-items: center; gap: 10px;">
      <img src="https://www.toothpasteapp.com/ToothPaste.png" alt="drawing" width="70"/>
      <span style="display: flex; flex-direction: column; align-items: center; line-height: 1;">
        <span style="font-weight: bold; font-size: 1.5em; margin: 1 0 5 0; padding: 0; line-height: 1;">ToothPaste V2: </span>
        <span style="font-style: italic; font-size: 0.6em; margin: 1 0 0 0; padding: 0; line-height: 1;">硬件级安全的 BLE 剪贴板。</span>
      </span>
    </span>
  </h1>
</div>

<div align="center" style="text-align: center; margin: 20px">
  <img src="https://img.shields.io/badge/c++-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white&logoSize=auto" alt="C++"/>
  <img src="https://img.shields.io/badge/espressif-E7352C.svg?style=for-the-badge&logo=espressif&logoColor=white&logoSize=auto" alt="Espressif"/>
  <img src="https://img.shields.io/badge/BLE-blue?style=for-the-badge&logo=bluetooth&logoColor=white&logoSize=auto" alt="BLE"/>
  <img src="https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E&logoSize=auto" alt="JavaScript"/>
  <img src="https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB&logoSize=auto" alt="React"/>
</div>



<p align="center" style="text-align: center; font-size: 1.2em;">
  <strong>ToothPaste</strong> 让你可以借助 Web BLE、一颗加密芯片(Cryptographic IC)和一颗 ESP32-S3,向任何兼容 USB 的设备无线发送经 <strong>AES-256</strong> 加密的键盘与鼠标指令——不需要专用驱动,也不需要繁琐的配置。
</p>

![ToothPaste 网站关于页缩略图](web/public/ToothPaste_Cover_V2.png)
<br/>

## 目录
- [问题的由来 ❓](#问题的由来-)
- [快速开始 📦](#快速开始-)
- [完整安装 🛠️](#完整安装-)
- [工作原理 Pt.1 ⭐](#工作原理-pt1-)
- [工作原理 Pt.2 ⭐⭐](#工作原理-pt2-)
- [硬件篇(PCBWay 天降神兵) 🔌](#硬件篇pcbway-天降神兵-)
- [安全性 🔑](#安全性-)
- [更多安全机制 🔒](#更多安全机制-)
- [然后就有了 AI 🤖](#然后就有了-ai-)
- [还有更多……](#还有更多)

# 问题的由来 ❓
> [!NOTE]
> 核心想法很简单:消除那些一次性场景中对复杂冗长登录流程的依赖——在这些场景里,通常只有键盘可用,或者说键盘是**唯一受支持的输入设备**(BIOS、物理隔离(air-gapped)系统、那些你死活不想装密码管理器的可疑小巷电脑等等)。

这意味着 [KDE Connect](https://github.com/KDE/kdeconnect-kde) 这类现有方案从一开始就行不通,因为它们至少要求两台设备都运行兼容的操作系统,并且允许安装第三方软件。

那么显而易见的答案,就是使用一种被普遍支持的接口系统——USB。准确地说,是 USB **人机接口设备(HID)**标准。几乎所有支持 USB 主机模式的设备都支持用键盘来控制它,而且由于键盘被视作用户的直接延伸,它会被默认信任(*键盘没有密码,因为你要用键盘才能输入密码* 😐)。

[Hak5 的 USB Rubber Ducky](https://hak5.org/products/usb-rubber-ducky?variant=39874478932081) 正是靠这个思路,掀起了一场利用设备漏洞的安全军备竞赛;不过这并不非得是使用它的唯一理由(当然,你想这么用也完全没问题 \**眨眼*\*)。

![在设备之间粘贴](web/public/ToothPasteBare.png)

### 在桌面版浏览器中运行 ToothPaste,控制一台 iPad
![ToothPasteDemo](web/public/ToothPasteDemoGif.gif)

### 在移动版浏览器中运行 ToothPaste,控制一台远程 Linux 机器
![ToothPasteDemoMobile](web/public/ToothPasteDemoMobile.gif)

# 快速开始 📦

> [!TIP]
> 最快的上手方式是打开 [ToothPaste 网页应用](https://www.toothpasteapp.com),点击 **Update(更新)**。它会打开一个 Web Serial 设备选择器,让你选中已连接的 ESP32-S3 设备并为其烧录固件。

> [!NOTE]
> ToothPaste 网页应用依赖 Web API 支持,而这目前只在 Brave、Edge、Chrome 等 Chromium 内核浏览器上可用。如果你是坚定的非 Chromium 党,建议使用桌面应用。

#### 或者,从 Releases 页面下载最新的 .bin 固件文件,然后使用 [esptool](https://github.com/espressif/esptool) / [espwebtool](https://esptool.spacehuhn.com/) 或类似的烧录工具进行烧录。

![更新提示](web/public/UpdatePrompt.png)

```“按键”指的是 GPIO0(在 ESP32 开发板上通常标注为 BOOT)```

# 完整安装 🛠️

如果因为某些原因,“简单模式”没能成功(通常是因为我把部署搞砸了),你可以从源码构建整个项目。

按照 [ESP-IDF(5.5.1 及以上)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/index.html) 的安装指南,构建 **firmware/** 文件夹中的内容。

如果你打算修改或创建自己的 ProtoBuf 数据包,还需要:
- [Protoc 编译器](https://protobuf.dev/installation/)
- [NanoPB](https://github.com/nanopb/nanopb)
- [ProtoBuf JS](https://github.com/protobufjs/protobuf.js)

# 工作原理 Pt.1 ⭐

我希望 ToothPaste 不需要太多前期配置就能快速上手。虽然做一个原生应用可以让“在本地与远程指令之间快速切换”的体验更轻松,但那是留给未来的我的问题。要做到这一点,同时保持半跨平台特性,最快的途径就是 [**Web BLE**](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)。

### 什么是 Web BLE?
如果你用过 [WLED](https://kno.wled.ge/) 或 [VIA](https://usevia.app/) 这类项目,那你其实已经接触过 [Web API](https://developer.mozilla.org/en-US/docs/Web/API) 了。这几乎是一项 Chromium 独占的功能,因此 **ToothPaste 网页应用**本身无法在 Firefox 等非 Chromium 浏览器上运行。

本质上,Web BLE 让我们可以在浏览器里直接使用系统的蓝牙硬件,从而不必为每个操作系统编写专属 API,也不需要配套的定制应用。


# 工作原理 Pt.2 ⭐⭐

ToothPaste 方案的另一部分(也是更有意思的部分)是硬件本身。由于 ESP32-S3 在一颗芯片里同时集成了 USB 和 BLE(外加一堆我们并不关心的其他外设),硬件最终只需要满足运行这颗 MCU 的最低要求即可。

对大多数爱好者来说,任意一块开发板都够用。但考虑到我们要在一个**相当**开放的协议上传输可能敏感的信息,ToothPaste V2.0 使用了一颗**加密协处理器**来存储加解密数据所需的凭据。

### ToothPaste V1.0 对比 V2.0
|  | ToothPaste V1.0 | ToothPaste V2.0 |
|----------|----------|----------|
| 跨平台 | ✅ | ✅ |
| 安全栈 | MBedTLS | MBedTLS + Cryptoauthlib |
| 凭据存储 | 软件绑定 🟠  | 硬件绑定 🟢 |
| 需要额外配置 | ❎ | ☑️ |

### 有请主角登场……

![ToothPaste 成品](web/public/ToothPasteIPad.png)


# 硬件篇(PCBWay 天降神兵) 🔌

你懂那种感觉吗:你以为自己终于把脑子里的所有想法都做成了真实的产品,结果**又一个想法冒了出来**?没错,ToothPaste 的硬件安全部分就是这么来的。

### 问题在于……
我意识到,对 ToothPaste 来说最 🤌 *完美* 🤌 的安全方案,应当使用加密 IC / 安全元件(Secure Element)/ TPM / \<随便什么听起来很酷的名词\>,把 ECDH 私钥保存在隔离的存储空间中,使得即使拥有设备的物理访问权也无法提取。Trezor 这类硬件加密货币钱包、YubiKey 这类硬件双因素认证方案,正是靠这种方式确保:就算不法之徒把你的实体设备抢到手,也永远碰不到里面的信息。

### [救星](https://www.pcbway.com/)登场……

问题在于,我当时已经设计并下单了 ToothPaste V1 的 PCB,而硬件开发又是个烧钱的爱好,我可不想仅仅出于热爱就把积蓄掏空。

就在这时,[PCBWay](https://www.pcbway.com/) 联系了我,说他们愿意赞助一个潜在 V2 版本的原型 PCB……
**于是我的第一反应是查一下这是不是封钓鱼邮件**。结果发现不是——在花了一个月手忙脚乱地研究各种可行方案之后,我联系了他们,把设计文件上传到他们的 PCB 下单工具,然后守在家门口~~耐心~~地等快递。

### 终于……

![ToothPaste V2.0](hardware/ToothPaste_V2_Cover_Annotated_PCBWay.png)

### **完美无瑕!美轮美奂!**

不用再手工焊接那个 USB-C 接口,差点让我热泪盈眶 🥲。PCBWay 还很贴心地允许我加订一个 USB-A 版本,因为我发现自己经常在老式台式机上想用 ToothPaste——没有 USB-C 接口的机器出现得太频繁,不能不给它留个位置。至于丝印上印什么,我可能(也可能没有)纠结了很久,最后选定了那个 *小小的* V2.0 标志——虽然小,细节却相当丰富。

**我也不必再担心会不会因为把 5V 和 3.3V 电源轨短路而再弄死一块 ESP32-S3(默哀),因为 PCBWay 已经替我完成了贴片和测试。**

但最棒的可能是再也不用自己去找元器件了。V1 给我留下的最大槽点之一,就是公头 USB-C 连接器只能找到**唯一一条商品链接**,而且运费比其余所有元件加起来还贵。我不知道他们是怎么做到的,也没问。反正 PCBWay 就这么神奇地变出了几个。我猜干 PCB 制造这一行 *可能* 有点关系。

ToothPaste V2 上的 Microchip [ATECC608B](https://www.microchip.com/en-us/product/atecc608b) CryptoAuth 芯片补上了硬件层面最后一块安全短板:私钥直接在芯片内部生成并保存,完全不会暴露给 ESP32 那并不安全的闪存。

遗憾的是,如何对这颗芯片编程是一段冒险故事,等我从各个角度确认不会因为说出 NDA 里的禁忌字眼而被 DMCA 投诉(顺带一提,我根本没收到过这份 NDA,谢谢啊 Microchip),我会在别的地方详述。

### 瞧瞧这个原始人 \*嗤之以鼻\*
![ToothPaste V1 手工搭建](firmware/images/ToothPaste_BOM.jpg)


# 安全性 🔑

蓝牙本身并不是一个安全的协议;较新的实现改变了这一点。如果不是贪恋这个极其灵活的跨平台发射器,我们本可以深入研究 BLE 支持的众多安全协议。

然而,截至目前 Web BLE 只支持 "just works"(直接配对)这一种认证方式,这实际上等于一条不设防的线路。考虑到 ToothPaste 在对方眼里就是一个键盘,而我的主要用途恰恰是向设备粘贴密码,[**中间人(MITM)攻击**](https://en.wikipedia.org/wiki/Man-in-the-middle_attack)就是一个非常现实的问题。

**因此我们必须确保:只有通过身份认证的设备,才被允许发送会被键入出去的数据。**

> [!IMPORTANT]
> 至于**为什么**没有选择其他密码学标准(说真的,关于各种方案优缺点的资料实在太多了),这里就不展开了。总之我决定采用两步加密流程:结合 [**ECDH 公钥密码学**](https://www.cloudflare.com/learning/ssl/how-does-public-key-encryption-work/) 与部分带外(OOB,*花哨的说法就是:密钥不经 BLE 传输*)的密钥交换,派生出一个对称 **AES-256** 密钥,并用它来加密 ToothPaste 数据包(_如果你够潮,也可以叫它 ToothPacket_)。

借助 [ATECC608B CryptoAuth 芯片](https://www.microchip.com/en-us/product/atecc608b),**ToothPaste V2.0** 还能保证:即使你把 ToothPaste 拆开、直接连上 ESP32-WROOM 模块的原始闪存,也找不到任何安全凭据的踪影。ATECC 会在自己隔离的闪存中生成并保存这些凭据,从不暴露给 ToothPaste 固件的其他部分;它的 I2C 总线上唯一会传出的信息,就是那个最终用于加密数据的会话级 AES-256 密钥。由于该密钥独一无二、且每次连接 ToothPaste 时都会重新生成,就算有人在会话断开之后拿到了它,也对我们毫无影响。

### 最终得到的是一套安全的通信体系:发射端与设备必须先完成配对流程,才能发送可能敏感的数据。

![ToothPaste 配对](web/public/Pairing.png)

# 更多安全机制 🔒

### ☀️ ToothPaste 完全本地化运行。没有服务器,没有常驻代理,也没有“守护”你数据的 SaaS 云原生妖精。

> [!CAUTION]
> 这意味着,如果有人能转储你浏览器中存储的 IndexedDB 数据,就能拿到你的 AES 密钥,并冒充发送指令的设备。
> _不过话说回来,要是有人都能做到这一步了,ToothPaste 恐怕是你最不用担心的事 💀_

### 🤷 但,因为我可以

ToothPaste 支持用“密码 + [Argon2](https://argon2-cffi.readthedocs.io/en/stable/argon2.html) 派生密钥”的方式加密这些本地数据,包括保存的宏(Macro)和 Duckyscript 脚本。
做法与带浏览器扩展的密码管理器完全一致。

![ToothPaste Argon2 加密](web/public/ToothPasteArgon.png)

# 然后就有了 AI 🤖

自从项目范围从“周末小玩意”一路膨胀成“每日执念”,我发现自己用 ToothPaste 操作树莓派这类设备时,大多数最常见的交互其实更像是在用 SSH。

有时候你只是想“搭一个基础网页服务器,加个前端,用来显示 GPIO3 上的传感器读数”。你清楚自己要做什么,这不是什么高精尖,甚至勉强算不上编程。可能只是跑一个脚本,或者几个……

条件允许的话,最好的选择是 SSH 进设备,让 LLM 接管剩下的活,直到它问你要不要执行 ```sudo rm -rf *```,你再礼貌地拒绝,然后继续过自己的日子。

### 但如果没法 SSH 呢

![ToothPasteDesktop 预览](web/public/ToothPaste_Desktop_Preview.png)

[ToothPasteDesktop](https://github.com/Brisk4t/ToothPasteDesktop) 用 Rust 实现了一个 **TUI 和 MCP 服务器**,让 AI 智能体可以控制 ToothPaste,并通过串口从远程系统获取响应。这条双向总线确实存在一些缺点:有的可以通过软件解决,有的则受制于硬件。

1. ESP32-S3 的 USB 端点数量有限。目前它们被以下功能占用:
   - BOOT 键盘接口(为了完整的 BIOS 支持)
   - BOOT 鼠标(更多的 BIOS 支持)
   - 通用 HID 输入(完整的键盘 + 鼠标支持)
   - 控制描述符(以上功能都离不开它)

这意味着(据我所知)必须牺牲其中之一,才能启用 USB CDC(串口)设备端点,让 ToothPaste 能够从所连接的设备读取数据。

如果在这一块能有更多余量,我想实现完整的 USB MSC(大容量存储设备类),让我们能够截取并查看屏幕画面——那基本上就能让 ToothPaste 变成一台基于 BLE 的 IP-KVM,类似于 [PiKVM](https://pikvm.org/) 通过传统 HTTP 做到的事情。

2. 通用大模型在缺少非常具体的指令和一定微调的情况下很难伺候。

让你喜欢的 MCP 兼容智能体“用 ToothPaste 发送按键”,成功率相当稳定;但如果不明确指示它“使用 > 操作符把数据通过管道写入 COMx 或 /dev/ttyx 上的串口设备,并等待有数据返回”,成功率就会大打折扣。

但我必须说,喊一句 ```Jarvis,打开 Chrome,放一首 JoJo 的 Roundabout``` 然后它真的就这么执行了——这份快乐相当独特。

当我在暗处悄悄开发 ToothPasteDesktop 的时候,如果你想先玩玩一个没打磨那么精细的版本,本仓库的 MCPerhaps 分支上有一个 Electron 应用,功能一样,只是……更笨重。

![未完待续](web/public/tobecontinued.png)

# 还有更多……

### 和所有凭热情驱动的项目一样,我有时会为了炫酷的新功能跑偏,忘了修好、测全所有东西。

#### 在 ToothPaste 网页应用中创建可重放的 Ducky 脚本。
![ToothPaste 脚本编写](web/public/ToothPasteScripting.png)


网页应用里还有一些功能,我会慢慢在这里补充文档;自从迷上 ToothPasteDesktop 的 Rust 之后,ToothPaste Web 就没怎么被精心照料过了。

ToothPaste 仍在持续开发中,但它终于到了我自己每天都在用的程度,所以我觉得是时候把它开源了。

如果你发现了出入,或者想以任何方式做出贡献,欢迎随时提 Issue;不过小弟我精力有限,审阅可能需要一些时间。

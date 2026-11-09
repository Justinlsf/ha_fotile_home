# Fotile 方太 - Home Assistant Integration

方太智能厨电 Home Assistant 官方集成插件，让方太油烟机、灶具等设备接入 Home Assistant，实现统一管理和智能联动。

> 中文版文档 | [English](README.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fotilefiks&repository=ha_fotile_home&category=integration)

---

## 支持设备

| 设备类型 | HA 实体 | 支持功能 |
|---------|---------|---------|
| 油烟机 | Fan | 总电源开关、三档风速（弱/自动/强） |
| 油烟机 | Light | 照明灯开关 |
| 灶具 | Binary Sensor ×2 | 左灶、右灶开启状态（**只读**） |

> **关于灶具**：方太开放给云云对接的灶具字段（`LeftStoveState` / `RightStoveState`）
> 读写权限为 `R`（只读），因此本集成只提供状态显示，**不提供灶具控制**。
>
> 更多品类（洗碗机、热水器、净水机、消毒柜等）将在方太提供对应物模型后陆续开放。
> 已删除的洗碗机与灶蒸烤平台代码保留在 git 历史中，待物模型到位后恢复。

### 设备类型如何识别

**不依赖 `devType` 字段**——方太云云对接规范未提供 `devType` 的取值对照表。
设备类别由 `DeviceDiscovery` 返回的 `services[].sid`（能力声明）判定，
见 `const.DEVICE_KIND_BY_SID`：

| 类别 | 命中以下任一 sid |
|------|-----------------|
| 油烟机 | `PowerSwitch` / `FanLevel` / `Light` |
| 灶具 | `LeftStoveState` / `RightStoveState` |

一台设备可同时命中多个类别（如集成灶），此时各平台实体都会创建。
每个实体还会二次校验该设备是否声明了对应 sid，
避免为不带灯的油烟机创建永远不可用的灯实体。

---

## 安装方式

### 方式一：HACS 安装（推荐）

1. 打开 Home Assistant → HACS → 集成
2. 搜索 **Fotile** 或 **方太**
3. 点击安装
4. 重启 Home Assistant

### 方式二：手动安装

1. 下载本仓库代码
2. 将 `custom_components/fotile` 文件夹复制到 Home Assistant 的 `custom_components` 目录
3. 重启 Home Assistant

---

## 配置

1. 进入 Home Assistant → 设置 → 设备与服务 → 添加集成
2. 搜索 **Fotile** 或 **方太**
3. 浏览器会跳转到**方太官网**，在方太的页面上用手机号 + 短信验证码登录并授权
4. 授权完成后自动返回 Home Assistant，系统自动发现并添加您账号下的所有方太设备

> **关于账号安全**：本集成采用 OAuth 2.0 授权码模式（Authorization Code + PKCE）。
> 您的登录、验证码输入全部发生在方太官网页面，**Home Assistant 不会接触、
> 也不会保存您的手机号、密码或验证码**，只持有一个可随时在方太侧撤销的访问令牌。

### 首次使用需要填入应用凭据

如果您使用的是方太官方发布的版本，凭据已内置，无需任何操作。

如果您是自行部署开发版本，则需要先在
「设置 → 设备与服务 → ⋮（右上角菜单）→ Application credentials」中
添加自己的 Client ID：

| 注册项 | 填写值 |
|--------|--------|
| 客户端类型 | 公共客户端 / 原生应用（public / native app） |
| 授权模式 | authorization_code + PKCE（S256） |
| 回调地址 | `https://my.home-assistant.io/redirect/oauth` |

> 回调地址必须**逐字符完全一致**。OAuth 2.1 要求精确字符串匹配，
> 前缀匹配或部分匹配都会被拒绝。

### 配置选项

安装后可在「设备与服务 → Fotile → 配置」中调整：

| 选项 | 说明 | 默认值 |
|------|------|--------|
| 更新间隔 | 设备状态刷新频率（秒） | 30（可设 10~300） |
| 设备筛选 | 仅接入勾选的设备；全部不勾选表示接入全部设备 | 全部设备 |

---

## 系统要求

- Home Assistant Core ≥ 2024.11.0
- 方太幸福家账号（需已绑定设备）
- 设备通过 WiFi 联网且在方太幸福家 APP 中在线
- 需能访问公网（本集成为云端轮询模式）

> 关于版本要求：集成使用了 Home Assistant 2024.11 引入的重新认证辅助方法，
> 在更早版本上会因缺少该 API 而无法正常工作。

---

## 云端协议说明

本集成对接方太云云互联协议，依据
《方太云云互联-方太集成开发者设备规范 V1.4(云云)》实现。

### 单端点 + namespace 分发（非 RESTful）

所有设备接口都 POST 到同一个地址，靠请求体内的 `header.namespace` 区分功能：

```
POST https://api-test.fotile.com/open-cloud/v1/api
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "header": {
    "namespace": "DeviceDiscovery",
    "thirdPartyId": "<CorpId>",
    "granteeId": "<CorpId>",
    "thirdPartyUserId": "<userId>",
    "messageId": "<uuid>",
    "timestamp": 1793356406787
  },
  "payload": { }
}
```

`thirdPartyId` 与 `granteeId` **都填方太颁发的 CorpId**（同值），
这是方太明确要求的，规范 2.1.4.1 中 `granteeId` 的描述即为
「第三方厂家标识(邮件中颁发的 CorpId)」。

| namespace | 用途 | 本集成使用位置 |
|-----------|------|---------------|
| `AcceptGrant` | 帐号授权（**前置必需**） | `config_flow.py`、`__init__.py` |
| `DeviceDiscovery` | 获取设备列表 | `coordinator.py` |
| `DeviceSnapshot` | 获取设备状态 | `coordinator.py` |
| `DeviceCommand` | 设备控制（写属性） | 各实体平台 |

### AcceptGrant 是前置条件

方太侧对 `AcceptGrant` 之外的所有 namespace 都会校验
`(userId, granteeId)` 是否已建立授权关系，未建立则返回 `10002 UNAUTHORIZED`。

集成在两处调用它：
1. `config_flow.py`——授权成功后立即调用，用返回的 `thirdPartyUserId` 作
   `unique_id`（防止同一方太账号被重复添加）并持久化；
2. `__init__.py`——集成加载时调用（已有持久化值则复用，避免重复请求）。

该接口幂等（服务端对已存在关系执行 update），重复调用安全。

### 控制是「写属性」而非「发动词指令」

```json
{
  "namespace": "DeviceCommand",
  "payload": {
    "command": {
      "timestamp": "20261030T103600Z",
      "thirdPartyDevId": "dev-hood-001",
      "prodId": "000b",
      "sid": "FanLevel",
      "data": { "FanLevel": 3 }
    }
  }
}
```

请求体里没有 `command` 动词名，只有 `sid`（服务标识）+ `data`（属性键值）。
注意 `command.timestamp` 格式为 `yyyyMMddTHHmmssZ`（无毫秒），
与快照里 `services[].ts` 的 `yyyyMMddTHHmmssSSSZ`（带毫秒）**不同**。

### 错误码走 body，不靠 HTTP 状态码

方太的业务错误通过 `payload.code` 表达。规范虽列出了对应的 HTTP 状态码，
但服务端的全局异常处理未设置 HTTP status，实现上很可能**恒返回 200**。

因此本集成**一律解析 `payload.code`**，遇以下凭据类错误码主动触发重新授权：
`10002` `100021` `100022` `10003` `10004` `10008` `10000` `100001`。
设备类错误（`10009` 设备不存在 / `10010` 不支持该操作 / `10011` 设备离线）
则抛 `FotileBusinessError`，不影响令牌状态。

### 状态数据是两层嵌套

```json
{ "devices": [{ "thirdPartyDevId": "...", "status": "online",
    "services": [{ "ts": "...", "sid": "PowerSwitch", "data": { "PowerSwitch": 1 } }] }] }
```

`core/mapping.py` 的 `flatten_service_data()` 把它摊平为 `{"PowerSwitch.PowerSwitch": 1}`，
用 `sid` 作前缀避免不同服务下的同名属性互相覆盖。
再由 `const.STATUS_FIELD_MAP` 映射为内部字段名供实体读取。

### 在线状态只来自快照

`DeviceDiscovery`（设备列表）**不提供在线状态**，
`online` 由 `DeviceSnapshot` 的 `status` 字段（`online`/`offline`）回填。

因此 `coordinator` 每轮必须对每台设备各发一次快照请求
（规范要求 `thirdPartyDevIds` 只传一个标识），已用 `asyncio.gather` 并发处理。
设备列表有 5 分钟缓存，不每轮都拉。

### 为什么不实现事件推送

规范 2.4 章定义了方太主动向第三方推送设备事件（`DeviceStatusChanged` 等），
但要求第三方提供**公网可访问的回调地址**。Home Assistant 通常是本地部署、
无公网入口，架构上收不到推送，故采用轮询模式
（`manifest.json` 中声明 `"iot_class": "cloud_polling"`）。

---

## 问题反馈

遇到问题请在 GitHub Issues 中提交，附上：
1. Home Assistant 版本
2. 设备型号
3. 日志信息（在 configuration.yaml 中启用调试日志）：

```yaml
logger:
  default: info
  logs:
    custom_components.fotile: debug
```

> 排查建议：先跑 `python tools/debug_auth.py devices --token <AT>`，
> 三步输出能直接定位问题在鉴权、设备列表还是状态解析环节。

---

## License

Apache License 2.0

# 企业信息查询接口

## 接口地址

```
POST /search_company_info
Content-Type: application/json
```

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `userid` | String | 是 | 用户ID |
| `userkey` | String | 是 | 32位认证密钥 |
| `companyName` | String | 是 | 企业名称（会自动 trim） |

### 请求示例

```json
{
  "userid": "test_user_001",
  "userkey": "7e5465a15b21fd751aea7774b58aafd2",
  "companyName": "珠海横琴航投一号投资中心（有限合伙）"
}
```

## 响应格式

所有响应统一包含 `code`、`msg`、`data` 三个字段。

### 1. 查询成功（code: 200）

```json
{
  "code": 200,
  "msg": "查询成功！",
  "data": {
    "companyName": "珠海横琴航投一号投资中心（有限合伙）",
    "usedTimes": 1,
    "remainingTimes": 99,
    "companyInfo": { ... }
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.companyName` | String | 查询的企业名称 |
| `data.usedTimes` | Number | 已使用次数（含本次） |
| `data.remainingTimes` | Number | 剩余可用次数 |
| `data.companyInfo` | Object | 扣子工作流返回的企业详细信息 |

### 2. 余额不足（code: 400）

```json
{
  "code": 400,
  "msg": "余额不足，请充值",
  "data": {
    "usedTimes": 100,
    "totalLimit": 100,
    "remainingTimes": 0,
    "rechargeUrl": "https://your-recharge-url.com",
    "companyInfo": null
  }
}
```

前端可直接用 `rechargeUrl` 做超链接跳转。

### 3. 参数错误 / 认证失败（code: 400）

```json
{
  "code": 400,
  "msg": "当前用户不存在，请输入正确的用户id！"
}
```

| msg | 触发条件 |
|---|---|
| `请求体不能为空且必须是JSON字符串` | body 为空或格式错误 |
| `JSON格式错误: ...` | JSON 解析失败 |
| `请求体中缺少 userid、userkey 或 companyName 参数` | 缺少必填参数或 companyName 为空 |
| `当前用户不存在，请输入正确的用户id！` | userid 在数据库中不存在 |
| `当前用户userkey不正确，请输入正确的userkey！` | userkey 不匹配 |

### 4. 服务调用失败（code: 500）

```json
{
  "code": 500,
  "msg": "Coze工作流调用失败: timeout",
  "data": {
    "usedTimes": 0,
    "totalLimit": 100,
    "remainingTimes": 100,
    "companyInfo": null
  }
}
```

**注意：服务调用失败不会扣费。**

## 错误码汇总

| code | 含义 |
|---|---|
| 200 | 查询成功 |
| 400 | 请求参数错误、认证失败或余额不足 |
| 500 | 扣子工作流调用失败 |

## 注意事项

1. **非幂等接口**：每次成功调用都会扣费，请避免重复提交
2. **失败不扣费**：扣子工作流调用失败（含重试）不扣余额，可以重试
3. **无并发保护**：高并发场景下同一用户短时间内多次请求可能超额扣费，建议前端控制调用频率
4. **超时**：扣子工作流调用超时时间为 30 秒，自动重试 2 次（间隔 1s / 2s）
5. **余额计算**：`remainingTimes = totalLimit - usedTimes`

# 企业信息查询服务 - 客户端接口文档

## 接口地址

```
POST https://你的云函数域名/company_search
Content-Type: application/json
```

## 请求格式

所有接口统一POST，通过 `method` 字段区分功能，`params` 传递参数：

```json
{
  "method": "方法名",
  "params": {
    "参数1": "值1",
    "参数2": "值2"
  }
}
```

## 统一响应格式

```json
{
  "code": 200,
  "msg": "描述信息",
  "data": { }
}
```

| code | 含义 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误 / 认证失败 / 余额不足 / 兑换码无效 |
| 403 | 管理员密钥错误 |
| 429 | 请求过于频繁（防暴试锁定） |
| 500 | 服务端错误 |

---

## 1. 查询企业信息

每次成功查询扣1次余额，查询失败不扣费。

### 请求

```json
{
  "method": "search",
  "params": {
    "userid": "test_user_001",
    "userkey": "7e5465a15b21fd751aea7774b58aafd2",
    "companyName": "珠海横琴航投一号投资中心（有限合伙）"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userid` | string | 是 | 用户ID |
| `userkey` | string | 是 | 32位认证密钥 |
| `companyName` | string | 是 | 企业名称 |

### 响应

**查询成功：**

```json
{
  "code": 200,
  "msg": "查询成功！",
  "data": {
    "companyName": "华为技术有限公司",
    "usedTimes": 1,
    "remainingTimes": 99,
    "companyInfo": {
      "data": {
        "Authority": "深圳市市场监督管理局",
        "BusinessScope": "一般经营项目：...(经营范围全文)",
        "CancelDate": null,
        "CancelReason": null,
        "City": "深圳市",
        "CityCode": "440300",
        "CompanyAddress": "深圳市龙岗区坂田华为总部办公楼",
        "CompanyCode": "440301103097413",
        "CompanyName": "华为技术有限公司",
        "CompanyPersonNum": 58435,
        "CompanyStatus": "存续（在营、开业、在册）",
        "CompanyStatusNew": "正常",
        "CompanyType": "有限责任公司(法人独资)",
        "CreditNo": "914403001922038216",
        "District": "龙岗区",
        "DistrictCode": "440307",
        "EstablishDate": "1987-09-15 00:00:00",
        "HistoryNameList": ["深圳市华为技术有限公司"],
        "HistoryNames": "深圳市华为技术有限公司",
        "Id": "912c15bb899cd061510ab8dd963e1420",
        "Industry": "计算机、通信和其他电子设备制造业",
        "IssueDate": "2026-04-28 00:00:00",
        "LegalPerson": "赵明路",
        "LegalPersonType": 1,
        "OperationEndDate": "2040-04-09 00:00:00",
        "OperationStartDate": "1987-09-15 00:00:00",
        "OrgCode": "192203821",
        "Province": "广东省",
        "ProvinceCode": "440000",
        "RealCapital": "4084113.182000万人民币",
        "RegCapital": "4104113.182000万人民币",
        "RegCapitalCurrency": "人民币",
        "RevokeDate": null,
        "RevokeReason": null,
        "TaxCode": "914403001922038216",
        "companyTypeTags": ["有限责任公司", "独资企业"],
        "industryAll": {
          "L1Name": "制造业",
          "L2Name": "计算机、通信和其他电子设备制造业",
          "L3Name": "通信设备制造",
          "L4Name": "通信系统设备制造"
        },
        "socialStaffNum": 58435
      }
    }
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.companyName` | string | 查询的企业名称 |
| `data.usedTimes` | number | 含本次的已使用次数 |
| `data.remainingTimes` | number | 剩余可用次数 |
| `data.companyInfo` | object | 企业详细信息（Coze 工作流返回） |

**companyInfo.data 字段明细：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `CompanyName` | string | 企业名称（现用名） |
| `CompanyAddress` | string | 企业住所地（完整地址） |
| `LegalPerson` | string | 法定代表人 |
| `CreditNo` | string | 统一社会信用代码 |
| `Province` / `City` / `District` | string | 省 / 市 / 区 |
| `ProvinceCode` / `CityCode` / `DistrictCode` | string | 行政区划代码 |
| `CompanyType` | string | 企业类型 |
| `CompanyStatus` | string | 经营状态（如"存续"） |
| `CompanyStatusNew` | string | 简化状态（如"正常"） |
| `HistoryNames` | string | 曾用名 |
| `HistoryNameList` | string[] | 曾用名列表 |
| `BusinessScope` | string | 经营范围 |
| `Industry` | string | 行业 |
| `industryAll` | object | 行业分类（L1-L4） |
| `RegCapital` / `RealCapital` | string | 注册资本 / 实缴资本 |
| `RegCapitalCurrency` | string | 注册资本币种 |
| `EstablishDate` | string | 成立日期 |
| `OperationStartDate` / `OperationEndDate` | string | 营业期限起止 |
| `IssueDate` | string | 核准日期 |
| `OrgCode` | string | 组织机构代码 |
| `TaxCode` | string | 税号 |
| `Authority` | string | 登记机关 |
| `CompanyPersonNum` / `socialStaffNum` | number | 人员规模 |
| `companyTypeTags` | string[] | 企业类型标签 |
| `CancelDate` / `CancelReason` | string/null | 注销日期/原因 |
| `RevokeDate` / `RevokeReason` | string/null | 吊销日期/原因 |

**余额不足：**

```json
{
  "code": 400,
  "msg": "余额不足，请充值",
  "data": {
    "usedTimes": 100,
    "totalLimit": 100,
    "remainingTimes": 0,
    "rechargeUrl": "https://pay.ldxp.cn/item/4tsgwq",
    "companyInfo": null
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.rechargeUrl` | string | 充值链接，前端可直接跳转 |

**用户认证失败：**

```json
{ "code": 400, "msg": "用户不存在" }
{ "code": 400, "msg": "用户密钥错误" }
```

**服务异常：**

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

> 服务异常不扣费，可以重试。

---

## 2. 查询余额

查询当前账户剩余次数，不扣费。

### 请求

```json
{
  "method": "getBalance",
  "params": {
    "userid": "test_user_001",
    "userkey": "7e5465a15b21fd751aea7774b58aafd2"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userid` | string | 是 | 用户ID |
| `userkey` | string | 是 | 32位认证密钥 |

### 响应

**成功：**

```json
{
  "code": 200,
  "msg": "查询成功",
  "data": {
    "userName": "张三",
    "usedTimes": 50,
    "totalLimit": 200,
    "remainingTimes": 150
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.userName` | string | 用户名 |
| `data.usedTimes` | number | 已使用次数 |
| `data.totalLimit` | number | 总额度 |
| `data.remainingTimes` | number | 剩余次数 |

**失败：**

```json
{ "code": 400, "msg": "用户不存在" }
{ "code": 400, "msg": "用户密钥错误" }
```

---

## 3. 兑换码充值

使用兑换码为账户充值，每个兑换码仅可使用一次。

### 请求

```json
{
  "method": "recharge",
  "params": {
    "userid": "test_user_001",
    "userkey": "7e5465a15b21fd751aea7774b58aafd2",
    "code": "ABCD-EFGH-JKLM"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userid` | string | 是 | 用户ID |
| `userkey` | string | 是 | 32位认证密钥 |
| `code` | string | 是 | 兑换码 |

### 响应

**充值成功：**

```json
{
  "code": 200,
  "msg": "充值成功，+100 次",
  "data": {
    "userName": "张三",
    "addTimes": 100,
    "beforeRemaining": 0,
    "afterRemaining": 100,
    "usedTimes": 50,
    "totalLimit": 150
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.userName` | string | 用户名 |
| `data.addTimes` | number | 本次充值次数 |
| `data.beforeRemaining` | number | 充值前剩余次数 |
| `data.afterRemaining` | number | 充值后剩余次数 |
| `data.usedTimes` | number | 累计已使用次数 |
| `data.totalLimit` | number | 总额度 |

**失败：**

```json
{ "code": 400, "msg": "用户不存在" }
{ "code": 400, "msg": "用户密钥错误" }
{ "code": 400, "msg": "兑换码不存在" }
{ "code": 400, "msg": "兑换码已使用或已过期" }
{ "code": 429, "msg": "尝试次数过多，请 180 秒后再试" }
{ "code": 500, "msg": "充值失败，请重试: ..." }
```

> 充值失败时兑换码不会被核销，可以重试。

### 防暴试机制

| 规则 | 说明 |
|------|------|
| 限制 | 同一用户20分钟内输错20次后锁定 |
| 锁定时间 | 20分钟，期间无法调用 recharge |
| 锁定响应 | `code: 429`，msg 提示剩余秒数 |
| 自动解除 | 20分钟后自动重置计数 |
| 成功重置 | 充值成功后立即清零错误计数 |

---

## 4. 生成兑换码

管理员专用，批量生成兑换码。

### 请求

```json
{
  "method": "generateCode",
  "params": {
    "adminKey": "your-admin-secret-key",
    "times": 100,
    "count": 5,
    "remark": "淘宝5月批次"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `adminKey` | string | 是 | 管理员密钥 |
| `times` | number | 是 | 每个兑换码的充值次数 |
| `count` | number | 否 | 生成数量，默认1，最大100 |
| `remark` | string | 否 | 备注 |

### 响应

**成功：**

```json
{
  "code": 200,
  "msg": "成功生成 5 个兑换码，每个 100 次",
  "data": [
    { "code": "ABCD-EFGH-JKLM", "times": 100 },
    { "code": "NPQR-STUV-WXYZ", "times": 100 },
    { "code": "2345-6789-ABCD", "times": 100 },
    { "code": "EFGH-JKLM-NPQR", "times": 100 },
    { "code": "STUV-WXYZ-2345", "times": 100 }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `data[].code` | string | 兑换码（格式XXXX-XXXX-XXXX） |
| `data[].times` | number | 该码的充值次数 |

**失败：**

```json
{ "code": 403, "msg": "管理员密钥错误" }
{ "code": 400, "msg": "充值次数必须大于0" }
{ "code": 400, "msg": "单次最多生成100个兑换码" }
```

---

## 5. 查询/导出兑换码

管理员专用，查询兑换码列表或导出为文本。

### 请求

**分页查询：**

```json
{
  "method": "listCodes",
  "params": {
    "adminKey": "your-admin-secret-key",
    "status": 0,
    "page": 1,
    "pageSize": 50
  }
}
```

**导出模式（一行一个兑换码，可直接复制到发码平台）：**

```json
{
  "method": "listCodes",
  "params": {
    "adminKey": "your-admin-secret-key",
    "status": 0,
    "exportCsv": true
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `adminKey` | string | 是 | 管理员密钥 |
| `status` | number | 否 | 状态筛选：0=未使用 1=已使用，不传则全部 |
| `page` | number | 否 | 页码，默认1 |
| `pageSize` | number | 否 | 每页数量，默认50，最大500 |
| `exportCsv` | boolean | 否 | 导出模式，true时返回一行一个的纯文本 |

### 响应

**分页查询成功：**

```json
{
  "code": 200,
  "msg": "查询成功",
  "data": {
    "total": 25,
    "page": 1,
    "pageSize": 50,
    "totalPages": 1,
    "list": [
      {
        "_id": "xxx",
        "code": "ABCD-EFGH-JKLM",
        "times": 100,
        "status": 0,
        "usedBy": null,
        "usedAt": null,
        "remark": "淘宝5月批次",
        "createTime": 1717000000000
      }
    ]
  }
}
```

**导出成功：**

```json
{
  "code": 200,
  "msg": "导出成功，共 25 个兑换码",
  "data": "ABCD-EFGH-JKLM\nNPQR-STUV-WXYZ\n2345-6789-ABCD\nEFGH-JKLM-NPQR\nSTUV-WXYZ-2345"
}
```

> `data` 为一行一个兑换码的纯文本，直接复制到发码平台即可。`status=0` 时只导出未使用的码。

---

## 错误码汇总

| code | 含义 | 可能的 msg |
|------|------|-----------|
| 200 | 成功 | 查询成功！/ 充值成功，+N 次 / ... |
| 400 | 客户端错误 | 缺少参数 / 用户不存在 / 用户密钥错误 / 余额不足，请充值 / 兑换码不存在 / 兑换码已使用或已过期 |
| 403 | 权限不足 | 管理员密钥错误 |
| 429 | 请求过于频繁 | 尝试次数过多，请 N 秒后再试 |
| 500 | 服务端错误 | Coze工作流调用失败 / 充值失败，请重试 |

---

## 调用示例

### cURL

```bash
# 查询企业
curl -X POST https://xxx.bspapp.com/company_search \
  -H "Content-Type: application/json" \
  -d '{"method":"search","params":{"userid":"test_user_001","userkey":"7e5465a15b21fd751aea7774b58aafd2","companyName":"华为技术有限公司"}}'

# 查询余额
curl -X POST https://xxx.bspapp.com/company_search \
  -H "Content-Type: application/json" \
  -d '{"method":"getBalance","params":{"userid":"test_user_001","userkey":"7e5465a15b21fd751aea7774b58aafd2"}}'

# 兑换码充值
curl -X POST https://xxx.bspapp.com/company_search \
  -H "Content-Type: application/json" \
  -d '{"method":"recharge","params":{"userid":"test_user_001","userkey":"7e5465a15b21fd751aea7774b58aafd2","code":"ABCD-EFGH-JKLM"}}'

# 生成兑换码（管理员）
curl -X POST https://xxx.bspapp.com/company_search \
  -H "Content-Type: application/json" \
  -d '{"method":"generateCode","params":{"adminKey":"your-admin-secret-key","times":100,"count":5}}'

# 查询兑换码列表（管理员）
curl -X POST https://xxx.bspapp.com/company_search \
  -H "Content-Type: application/json" \
  -d '{"method":"listCodes","params":{"adminKey":"your-admin-secret-key","status":0,"page":1,"pageSize":50}}'

# 导出兑换码（管理员）
curl -X POST https://xxx.bspapp.com/company_search \
  -H "Content-Type: application/json" \
  -d '{"method":"listCodes","params":{"adminKey":"your-admin-secret-key","status":0,"exportCsv":true}}'
```

### Python

```python
import requests

BASE_URL = "https://xxx.bspapp.com/company_search"

def call(method, params):
    return requests.post(BASE_URL, json={"method": method, "params": params}).json()

# 查询企业
call("search", {"userid": "test_user_001", "userkey": "xxx", "companyName": "华为技术有限公司"})

# 查询余额
call("getBalance", {"userid": "test_user_001", "userkey": "xxx"})

# 兑换码充值
call("recharge", {"userid": "test_user_001", "userkey": "xxx", "code": "ABCD-EFGH-JKLM"})

# 生成兑换码
call("generateCode", {"adminKey": "your-admin-secret-key", "times": 100, "count": 5})

# 导出兑换码
call("listCodes", {"adminKey": "your-admin-secret-key", "status": 0, "exportCsv": True})
```

### JavaScript

```javascript
const BASE_URL = "https://xxx.bspapp.com/company_search";

async function call(method, params) {
  const res = await fetch(BASE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, params })
  });
  return res.json();
}

// 查询企业
call("search", { userid: "test_user_001", userkey: "xxx", companyName: "华为技术有限公司" });

// 查询余额
call("getBalance", { userid: "test_user_001", userkey: "xxx" });

// 兑换码充值
call("recharge", { userid: "test_user_001", userkey: "xxx", code: "ABCD-EFGH-JKLM" });
```

---

## 注意事项

1. **非幂等**：`search` 每次成功调用扣1次，避免重复提交
2. **失败不扣费**：Coze工作流调用失败不扣余额
3. **兑换码一次性**：使用后无法再次使用
4. **充值原子性**：兑换码核销与余额增加在同一事务中，失败自动回滚
5. **超时重试**：Coze工作流超时30秒，自动重试2次（间隔1s/2s）
6. **余额公式**：`remainingTimes = totalLimit - usedTimes`
7. **防暴试**：同一用户20分钟内输错20次兑换码后锁定20分钟
8. **充值链接**：余额不足时响应中包含 `rechargeUrl`，前端可直接跳转

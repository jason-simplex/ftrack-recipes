# Note History Action - 多语言支持

这个脚本现在支持多语言界面，可以通过配置文件切换中文和英文界面。

## 文件结构

```
hook/
├── note_history.py          # 主脚本文件
├── config.json             # 配置文件
├── languages/              # 语言文件目录
│   ├── cn.json            # 中文语言文件
│   └── en.json            # 英文语言文件
└── README.md              # 说明文档
```

## 配置说明

### config.json
配置文件用于设置当前使用的语言：

```json
{
    "language": "CN",
    "available_languages": ["CN", "EN"]
}
```

- `language`: 当前使用的语言，支持 "CN"（中文）和 "EN"（英文）
- `available_languages`: 可用的语言列表

### 语言文件

语言文件位于 `languages/` 目录下：

- `cn.json`: 中文界面文本
- `en.json`: 英文界面文本

每个语言文件包含以下部分：

- `action`: Action的标签和描述
- `interface`: 用户界面文本
- `launch`: 执行结果相关文本
- `operations`: 操作类型标签（创建、更新、删除）
- `logging`: 日志信息文本

## 使用方法

### 切换语言

1. 编辑 `config.json` 文件
2. 将 `language` 字段改为所需语言：
   - `"CN"` - 中文界面
   - `"EN"` - 英文界面
3. 重新启动脚本或重新加载 ftrack-connect 插件

### 示例

**切换到英文界面：**
```json
{
    "language": "EN",
    "available_languages": ["CN", "EN"]
}
```

**切换到中文界面：**
```json
{
    "language": "CN",
    "available_languages": ["CN", "EN"]
}
```

## 错误处理

- 如果配置文件不存在或格式错误，将使用默认的中文配置
- 如果指定的语言文件不存在，将自动回退到中文语言文件
- 如果所有语言文件都无法加载，将使用内置的默认中文文本

## 添加新语言

要添加新的语言支持：

1. 在 `languages/` 目录下创建新的语言文件（如 `jp.json`）
2. 复制 `cn.json` 的结构，翻译所有文本内容
3. 在 `config.json` 中添加新语言到 `available_languages` 列表
4. 设置 `language` 字段为新语言代码

## 注意事项

- 语言代码不区分大小写（CN、cn、Cn 都可以）
- 修改配置后需要重新启动脚本才能生效
- 确保语言文件的 JSON 格式正确，否则会回退到默认语言
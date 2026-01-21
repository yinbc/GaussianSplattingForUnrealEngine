# 高斯溅射颜色偏暗问题诊断与解决

## 问题描述

渲染出来的高斯溅射颜色比编辑器中看到的偏暗。

## 可能的原因

### 1. ✅ PLY加载时的双重Gamma校正（已修复）

**问题**：在 `GaussianSplattingPointCloud.cpp:257` 中，颜色经过了双重gamma校正。

**状态**：✅ 已在提交 `3286cf9` 中修复

```cpp
// 修复前：
Point.Color = SRGBToLinear(Color);  // ❌ 双重转换

// 修复后：
Point.Color = Color;  // ✅ 直接使用线性颜色
```

### 2. 🔍 HDR和色调映射

**问题**：Unreal Engine的HDR渲染管线会应用**色调映射（Tone Mapping）**，这可能压暗颜色。

#### 色调映射的影响

| 阶段 | 颜色空间 | 说明 |
|------|---------|------|
| 材质输出 | Linear HDR | 线性空间，可能 > 1.0 |
| 色调映射 | → | 将HDR映射到0-1范围 |
| 最终显示 | sRGB LDR | 显示器显示的颜色 |

**诊断方法**：

1. 在编辑器中打开 **后处理体积（Post Process Volume）**
2. 查看 **色调映射器（Tone Mapper）** 设置
3. 检查 **曝光（Exposure）** 设置

#### 解决方案

##### 方案A：调整项目的色调映射设置

在 **项目设置（Project Settings）** 中：

```
编辑 → 项目设置 → 引擎 → 渲染 → 后处理
```

调整以下参数：

- **Tone Mapper** → 选择 `ACES Filmic` 或 `None`
- **Auto Exposure** → 关闭或调整
- **Exposure Compensation** → 增加0.5-1.0

##### 方案B：在材质中补偿

如果项目色调映射设置无法更改，可以在材质中增加颜色强度：

1. 打开 `Content/Materials/M_GaussianSplatting.uasset`
2. 在颜色输出前添加 **Multiply** 节点
3. 乘以 `2.0` 或 `2.5`（根据实际效果调整）

##### 方案C：使用Emissive（发光）

将高斯点设置为发光材质，绕过色调映射：

1. 材质输出连接到 **Emissive Color** 而不是 **Base Color**
2. 发光颜色不受色调映射影响

### 3. 🔍 Niagara材质设置

如果使用Niagara System渲染，检查以下设置：

#### Niagara Sprite Renderer设置

```
NS_GaussianSplattingPointCloud
  └─ Sprite Renderer
      └─ Material
          └─ Blend Mode: 应该是 Translucent 或 Additive
```

#### 材质Domain设置

打开Niagara使用的材质，确认：
- **Material Domain**: `Surface` 或 `User Interface`
- **Blend Mode**: `Translucent` 或 `Masked`
- **Shading Model**: `Unlit`（无光照，不受光照影响）

### 4. 🔍 纹理压缩设置

**当前设置**（`GaussianSplattingEditorLibrary.cpp:305-306`）：

```cpp
NewTexture->CompressionSettings = TC_HDR;  // HDR压缩
NewTexture->SRGB = false;  // ✅ 正确：线性空间
```

这是正确的配置。如果修改为 `SRGB = true` 会导致颜色再次被gamma校正而变暗。

### 5. 🔍 后处理体积设置

场景中的后处理体积可能影响颜色：

#### 检查项

1. **World Outliner** → 搜索 `PostProcessVolume`
2. 检查以下设置：

| 设置项 | 推荐值 | 说明 |
|--------|--------|------|
| **Auto Exposure Bias** | 0.0 - 1.0 | 增加整体亮度 |
| **Min Brightness** | 0.5 - 1.0 | 提高最暗亮度 |
| **Max Brightness** | 2.0 - 4.0 | 允许更亮的颜色 |
| **Tone Mapper Slope** | 0.8 - 1.0 | 调整对比度曲线 |

#### 创建测试后处理体积

```
1. 在场景中放置 Post Process Volume
2. 勾选 "Unbound"（影响全场景）
3. 启用 "Auto Exposure"
4. 设置 "Exposure Compensation" = 1.0
5. 禁用 "Color Grading" 避免额外颜色调整
```

## 快速测试步骤

### 测试1：禁用色调映射

1. 打开 **控制台命令（~键）**
2. 输入：`r.TonemapperFilm 0`
3. 观察颜色变化

如果颜色变正常，说明是色调映射问题。

### 测试2：增加曝光

控制台命令：
```
r.Exposure.Compensation 1.0
```

逐步增加到 `2.0` 或 `3.0` 查看效果。

### 测试3：对比原始颜色

在材质中输出纯色测试：

1. 临时修改材质，直接输出 `float3(1, 0, 0)` （纯红）
2. 如果纯红色也偏暗，说明是渲染管线问题
3. 如果纯红色正常，说明是颜色数据问题

## 推荐的配置

### 最佳实践配置

```cpp
// 在PostProcessVolume中设置：
struct FPostProcessSettings Settings;
Settings.bOverride_AutoExposureBias = true;
Settings.AutoExposureBias = 1.0f;  // 增加曝光

Settings.bOverride_ToneCurveAmount = true;
Settings.ToneCurveAmount = 0.0f;  // 减少色调曲线影响

Settings.bOverride_ExpandGamut = true;
Settings.ExpandGamut = 1.0f;  // 扩展色域
```

### 材质Shader建议

如果需要在材质中直接补偿，可以：

```hlsl
// 伪代码：在材质图表中
float3 Color = Texture2D.Sample(ColorTexture, UV).rgb;
Color = Color * 2.0;  // 简单的亮度提升
return Color;
```

## 验证修复

### 对比检查清单

- [ ] PLY加载不再有双重gamma校正
- [ ] 纹理 SRGB 标志为 false
- [ ] 后处理色调映射已调整
- [ ] 曝光补偿已增加
- [ ] Niagara材质为Unlit模式
- [ ] 测试场景中颜色与编辑器预览一致

## 相关代码位置

| 功能 | 文件 | 行号 |
|------|------|------|
| PLY颜色加载 | `GaussianSplattingPointCloud.cpp` | 250-259 |
| 纹理创建 | `GaussianSplattingEditorLibrary.cpp` | 295-307 |
| 颜色数据写入 | `GaussianSplattingEditorLibrary.cpp` | 162-167 |
| 场景捕获设置 | `GaussianSplattingStep.cpp` | 166, 327, 661 |

## 其他可能的原因

### 光照影响

如果材质是 **Lit（受光照）** 而不是 **Unlit（无光照）**：
- 场景光照可能使高斯点变暗
- **解决方案**：将材质改为Unlit

### Gamma显示

某些显示器或系统设置可能有额外的gamma校正：
- 检查显示器OSD设置
- 检查GPU驱动的gamma设置

## 总结

颜色偏暗最可能的原因是 **HDR色调映射**。建议优先尝试：

1. ✅ 确认PLY加载修复已生效（重新编译）
2. 🔥 调整后处理曝光补偿（最简单）
3. 🔧 修改材质使用Emissive输出（最可靠）
4. ⚙️ 调整项目色调映射设置（全局影响）

# COLMAP导出功能说明

## 概述

本功能允许将高斯溅射点云导出为COLMAP格式,方便与其他三维重建工具进行数据交换。

## 功能特性

- ✅ 支持将PLY格式的高斯点云导出为COLMAP `points3D.bin/txt`格式
- ✅ 自动转换坐标系和颜色空间
- ✅ 支持二进制和文本两种COLMAP格式
- ✅ 可选创建虚拟相机和图像文件,生成完整的COLMAP重建模型

## 使用方法

### 1. 在蓝图中使用

#### 方法1: 从PLY文件导出

```cpp
// C++示例
bool Success = UGaussianSplattingEditorLibrary::ExportPlyToColmap(
    TEXT("/Path/To/point_cloud.ply"),      // PLY文件路径
    TEXT("/Path/To/Output/colmap"),        // 输出目录
    true,                                   // 使用二进制格式
    false                                   // 不创建虚拟相机
);
```

#### 方法2: 使用别名函数导出

```cpp
// C++示例（ExportPointCloudToColmap 是 ExportPlyToColmap 的别名）
bool Success = UGaussianSplattingEditorLibrary::ExportPointCloudToColmap(
    TEXT("/Path/To/point_cloud.ply"),      // PLY文件路径
    TEXT("/Path/To/Output/colmap"),        // 输出目录
    true,                                   // 使用二进制格式
    false                                   // 不创建虚拟相机
);
```

### 2. 函数参数说明

#### ExportPlyToColmap

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `PlyFilePath` | FString | PLY文件的完整路径 |
| `OutputDirectory` | FString | COLMAP文件输出目录 |
| `bBinaryFormat` | bool | true=二进制格式(.bin), false=文本格式(.txt) |
| `bCreateDummyCamera` | bool | 是否创建虚拟相机和图像文件 |

#### ExportPointCloudToColmap

**注意**: 此函数是 `ExportPlyToColmap` 的别名，参数相同。

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `PlyFilePath` | FString | PLY文件的完整路径 |
| `OutputDirectory` | FString | COLMAP文件输出目录 |
| `bBinaryFormat` | bool | true=二进制格式(.bin), false=文本格式(.txt) |
| `bCreateDummyCamera` | bool | 是否创建虚拟相机和图像文件 |

### 3. 输出文件说明

#### 仅导出点云 (`bCreateDummyCamera = false`)

输出文件:
- `points3D.bin` 或 `points3D.txt` - 3D点云数据

#### 导出完整模型 (`bCreateDummyCamera = true`)

输出文件:
- `cameras.bin/txt` - 虚拟相机参数
- `images.bin/txt` - 虚拟图像位姿
- `points3D.bin/txt` - 3D点云数据

## COLMAP格式数据结构

### Point3D格式

每个3D点包含以下信息:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | uint64 | 点ID (从1开始) |
| `xyz` | double[3] | 3D坐标 |
| `rgb` | uint8[3] | RGB颜色 (0-255) |
| `error` | double | 重投影误差 (基于透明度计算) |
| `image_ids` | int32[] | 关联的图像ID列表 (导出时为空) |
| `point2D_idxs` | int32[] | 关联的2D点索引列表 (导出时为空) |

## 数据转换说明

### 坐标系转换

PLY文件中的坐标直接使用,无需额外转换(假设PLY已经是COLMAP坐标系)。

### 颜色转换

1. PLY的SH0系数 → 线性RGB
   ```
   linear_rgb = C0 * f_dc + 0.5
   ```

2. 线性RGB → sRGB
   ```
   srgb = linear_to_srgb(linear_rgb)
   ```

3. sRGB → 0-255整数
   ```
   rgb = srgb * 255
   ```

其中 `C0 = 0.28209479177387814` (SH0系数)

### 误差计算

基于PLY中的opacity值:
```
opacity_value = 1 / (1 + exp(-opacity))
error = 1 - opacity_value
```

透明度越高的点,误差越低。

## 前置要求

1. **Python环境**: 需要配置Python可执行文件路径
   - 打开: 编辑 → 项目设置 → Gaussian Splatting
   - 设置: Python Executable Path

2. **Python依赖库**:
   ```bash
   pip install numpy plyfile
   ```

3. **Scripts目录**: 确保 `export_colmap.py` 存在于插件的 `Scripts` 目录中

## 常见问题

### Q1: 导出失败,提示找不到Python

**A:** 请在项目设置中配置Python可执行文件路径:
1. 编辑 → 项目设置 → Gaussian Splatting
2. 设置 Python Executable Path (例如: `C:/Python39/python.exe`)

### Q2: 导出的点云颜色不正确

**A:** 这是正常的,因为:
1. 高斯溅射使用球谐函数(SH)表示颜色,具有视角相关性
2. 导出时只使用SH0系数(DC分量),代表平均颜色
3. 如需完整的视角相关颜色,需要保留完整的SH系数

### Q3: 两个导出函数有什么区别？

**A:** `ExportPointCloudToColmap` 和 `ExportPlyToColmap` 功能完全相同，前者只是后者的别名，为了保持API的一致性而保留。建议直接使用 `ExportPlyToColmap`。

### Q4: COLMAP无法读取导出的文件

**A:** 请检查:
1. 确保使用二进制格式 (`bBinaryFormat = true`)
2. 确认COLMAP版本支持该格式
3. 如果问题仍存在,尝试文本格式 (`bBinaryFormat = false`)

## 技术实现

导出功能由以下组件实现:

1. **Python脚本**: `Scripts/export_colmap.py`
   - 读取PLY文件
   - 转换数据格式
   - 写入COLMAP文件

2. **C++接口**: `GaussianSplattingEditorLibrary`
   - `ExportPlyToColmap()` - PLY文件导出
   - `ExportPointCloudToColmap()` - PLY文件导出（别名函数）

3. **COLMAP工具**: `Scripts/read_write_model.py`
   - COLMAP格式读写库

## 参考资料

- [COLMAP官方文档](https://colmap.github.io/)
- [COLMAP格式说明](https://colmap.github.io/format.html)
- [3D Gaussian Splatting论文](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/)

## 版本历史

- **v1.0** (2026-01): 初始版本
  - 支持PLY到COLMAP points3D的转换
  - 支持二进制和文本格式
  - 可选创建虚拟相机模型

# 鼠标跟随助手 · Windows

用于已测试小游戏的视觉跟随桌面程序。自动发现游戏画面，锁定初始白色目标，结合背景运动补偿和初始形状拟合持续跟随。

- Windows 10/11 x64，双击运行；默认预览，勾选后接管真实鼠标。
- Esc 紧急停止，F8 暂停/恢复；丢失画面、低匹配、结束提示或到期即停止指针控制。
- 一机一码：永久、30 天、3 天体验，离线 Ed25519 签名。
- 管理员签发工具单独构建；私钥不在仓库和任何 exe 中。
- GitHub Actions 在 Windows 构建使用者客户端、管理员永久自用版和授权签发工具三个独立 exe 并运行自检。

[用户说明](docs/USER-GUIDE.md) · [管理员说明](docs/OWNER-GUIDE.md)

## 开发运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python client_main.py
```

公钥必须为部署者的真实公钥。仓库中已配置此部署公钥，不使用共享演示私钥。首次另建部署：

```powershell
python -m admin.issuer keygen --private C:\OwnerSecrets\owner-private.pem --public follower\assets\license-public.pem
```

构建：`./build_windows.ps1`，或在仓库 Actions 运行 `Build Windows EXE`。

## 目录

- `follower/`：检测、实时视觉跟踪、设备绑定授权、Windows 输入、桌面 UI。
- `admin/`：管理员离线签发 CLI/GUI；不进入客户端 exe。
- `tests/`：签名、期限、防篡改、视觉检测、屏幕坐标、分发隔离测试。
- `.github/workflows/windows-build.yml`：Windows 构建与产物。

识别仍可能偏离；必须提供目标最初的白色阶段。完全离线授权存在常见的本地绕过边界，详见管理员说明。此仓库不包含用户录屏、实验缓存或私钥。

## 管理员永久自用版

Actions 产物 `MouseFollowerAdmin-Permanent-Windows-x64` 内的 `MouseFollowerAdmin.exe` 无需设备码和激活码，永久使用。只供所有者保管，不要分发给使用者。详见 [管理员自用说明](docs/ADMIN-EDITION.md)。

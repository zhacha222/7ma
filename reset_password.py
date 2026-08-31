import sys
import getpass

import settings_store


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    if args and args[0] in ("-h", "--help"):
        print("用法: python reset_password.py [新密码]")
        print("不带参数时以交互方式输入并确认新密码。")
        return 0

    if args:
        new_password = args[0]
    else:
        new_password = getpass.getpass("请输入新的管理员密码: ")
        confirm = getpass.getpass("请再次输入确认: ")
        if new_password != confirm:
            print("两次输入不一致，已取消。")
            return 1

    if len(new_password) < 4:
        print("密码至少 4 位。")
        return 1

    settings_store.set_password(new_password)
    print(f"管理员密码已更新为：{new_password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

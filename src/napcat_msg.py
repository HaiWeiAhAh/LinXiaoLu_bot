import uuid


class Group_Msg:
    def __init__(self,group_id,echo:str = None):
        self.group_id = group_id
        self.echo = echo or str(uuid.uuid4())
        self.msg = []
    async def build_text_msg(self,text:str):
        text_msg = {"type": "text", "data": {"text": text}}
        self.msg.append(text_msg)
    async def build_image_msg(self,image:str):
        image_msg = {
            "type": "image",
            "data": {
                # 本地路径
                "file": image,
                "summary": "[图片]"
                # 网络路径
                # "file": "http://i0.hdslb.com/bfs/archive/c8fd97a40bf79f03e7b76cbc87236f612caef7b2.png"
                #base64编码
                # "file": "base64://xxxxxxxx"
            }
        }
        self.msg.append(image_msg)
    async def build_at_msg(self,at_qq:int|str):
        at_msg = {
            "type": "at",
            "data": {
                "qq": f"{at_qq}", #all为艾特全体
            }
        }
        self.msg.append(at_msg)
    async def build_reply_msg(self,reply_msg_id:int|str):
        reply_msg = {
            #第一个必须为reply
            "type": "reply",
            "data": {
                "id": reply_msg_id
            }
        }
        self.msg.insert(0,reply_msg)
    async def build_file_msg(self,file_name:str,file):
        file_msg = {
            "type": "file",
            "data": {
                # 本地路径
                "file": file,

                # 网络路径
                # "file": "http://i0.hdslb.com/bfs/archive/c8fd97a40bf79f03e7b76cbc87236f612caef7b2.png",

                # "file": "base64或DataUrl编码",

                "name": file_name
            }
        }
        self.msg.append(file_msg)

    async def initialization_msg(self,msg:list):
        init_msg = []
        other_msg = []
        try:
            for msg_type in msg:
                #规范消息的规则
                if msg_type.get("type") == "reply":#规则1：reply的消息必须放在消息的首位
                    init_msg.append(msg_type)
                else:
                    other_msg.append(msg_type)
            #拼接所有消息
            init_msg.extend(other_msg)
            return init_msg
        except Exception as e:
            print(f"初始化消息对象出错：({e})，以默认返回初始值")
        return init_msg
    async def return_complete_websocket_payload(self):
        msg = await self.initialization_msg(msg=self.msg)

        return {
            "action": "send_group_msg",
            "echo" : self.echo,
            "params":{
            "group_id": self.group_id,
            "message": msg
            }
        }
    async def return_complete_http_payload(self):
        return {
            "action": "send_group_msg",
            "echo": self.echo,
            "group_id": self.group_id,
            "message": self.msg
        }
class File_Msg:
    def __init__(self,file,name,folder):
        self.file_id = file
        self.name = name
        self.folder = folder
    async def build_upload_file_msg(self):
        pass

class MsgOs_Msg:
    def __init__(self,file):
        self.file = file
    async def build_delete_file_msg(self):
        pass
def choice_send_tpye(payload:dict,send_type:str):
    return {
        "send_type": send_type,
        "payload": payload
    }
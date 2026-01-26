
class Group_Msg:
    def __init__(self,group_id):
        self.group_id = group_id
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
    async def build_reply_msg(self,reply_qq:int):
        reply_msg = {
            #第一个必须为reply
            "type": "reply",
            "data": {
                "id": reply_qq
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
    async def return_complete_payload(self):
        return {
            "action": "send_group_msg",
            "params":{
            "group_id": self.group_id,
            "message": self.msg
            }
        }
class File_Msg:
    def __init__(self,file,name,folder):
        self.file_id = file
        self.name = name
        self.folder = folder
    async def build_upload_file_msg(self):
        pass

def choice_send_tpye(payload:dict,send_type:str):
    return {
        "send_type": send_type,
        "payload": payload
    }
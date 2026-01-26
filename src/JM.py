from jmcomic import *

def search_comic(comic_keyword: str | int, max_count: int = 5)->str|None:
    client = JmOption.default().new_jm_client()
    result =[]
    if isinstance(comic_keyword, str):
        # 分页查询，search_site就是禁漫网页上的【站内搜索】
        try:
            page: JmSearchPage = client.search_site(search_query=comic_keyword, page=1)
        except MissingAlbumPhotoException as e:
            print(f'id={e.error_jmid}的本子不存在')

        except JsonResolveFailException as e:
            print(f'解析json失败')
            # 响应对象
            resp = e.resp
            print(f'resp.text: {resp.text}, resp.status_code: {resp.status_code}')

        except RequestRetryAllFailException as e:
            print(f'请求失败，重试次数耗尽')

        except JmcomicException as e:
            # 捕获所有异常，用作兜底
            print(f'jmcomic遇到异常: {e}')
        result.append(f'结果总数: {page.total}, 分页大小: {page.page_size}，页数: {page.page_count}')
        #print(f'结果总数: {page.total}, 分页大小: {page.page_size}，页数: {page.page_count}')

        # page默认的迭代方式是page.iter_id_title()，每次迭代返回 albun_id, title
        i = 0
        for album_id, title in page:
            if i < max_count:
                i = i + 1
                result.append(f"车号{album_id}:{title}")
                #print(f'[{album_id}]-[{i}]: {title}')
            else:
                break
    elif  isinstance(comic_keyword, int):
        # 直接搜索禁漫车号
        try:
            page = client.search_site(search_query=comic_keyword)
        except MissingAlbumPhotoException as e:
            print(f'id={e.error_jmid}的本子不存在')

        except JsonResolveFailException as e:
            print(f'解析json失败')
            # 响应对象
            resp = e.resp
            print(f'resp.text: {resp.text}, resp.status_code: {resp.status_code}')

        except RequestRetryAllFailException as e:
            print(f'请求失败，重试次数耗尽')

        except JmcomicException as e:
            # 捕获所有异常，用作兜底
            print(f'jmcomic遇到异常: {e}')
        album: JmAlbumDetail = page.single_album
        result.append(f"{album.name}:总页数:{album.page_count},发布日期:{album.pub_date}更新日期：{album.update_date},作者:{' and '.join(album.authors)},观看数:{album.views},评论数:{album.comment_count}")
        result.append(f"tag:{'-'.join(album.tags)}")
    else:
        #print("comic_keyword未知的类型，跳过")
        return "unknown"
    return "\n".join(result)

async def download_comics(comic_id:int):
    option = create_option_by_file('myoption.yml')
    try:
        download_album(comic_id,option)
        pdf_path = f"/root/LinXiaoLu_bot/JM-pdf/{comic_id}.pdf"
        filename = os.path.basename(pdf_path)

        async with aiofiles.open(pdf_path, mode='rb') as f:
            file_data = await f.read()
        return file_data
    except MissingAlbumPhotoException as e:
        print(f'id={e.error_jmid}的本子不存在')

    except JsonResolveFailException as e:
        print(f'解析json失败')
        # 响应对象
        resp = e.resp
        print(f'resp.text: {resp.text}, resp.status_code: {resp.status_code}')

    except RequestRetryAllFailException as e:
        print(f'请求失败，重试次数耗尽')

    except JmcomicException as e:
        # 捕获所有异常，用作兜底
        print(f'jmcomic遇到异常: {e}')

import {$, json, countView, viewCount} from './common.js';

async function openReading() {
  const id = new URLSearchParams(location.search).get('id');
  const list = await json('data/articles.json');
  const article = list.find(item => item.id === id);
  if (!article) throw new Error('没有找到这篇文章，请返回精读总览。');
  if (!/^readings\/[a-zA-Z0-9_-]+\.html$/.test(article.path)) {
    throw new Error('文章路径无效。');
  }
  $('#reader-title').textContent = article.title;
  document.title = article.title + ' · StarCape';
  const response = await fetch(article.path, {cache: 'no-store'});
  if (!response.ok) throw new Error('文章文件暂时不可用，请返回总览重试。');
  const html = await response.text();
  const frame = $('#reader-frame');
  frame.srcdoc = html;
  frame.hidden = false;
  const saved = countView(id);
  $('#reader-status').textContent = `期次 ${article.edition} · 更新 ${article.updated} · ${saved ? viewCount(id) + ' 次本机查看' : '浏览器禁止保存查看次数'} · 原文日期 ${article.published || '未填写'}`;
}

try {
  await openReading();
} catch (error) {
  $('#reader-title').textContent = '暂时无法打开';
  $('#reader-status').textContent = error.message;
}

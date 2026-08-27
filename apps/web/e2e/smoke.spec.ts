import { test, expect } from '@playwright/test'

test('login, open persona, send message, see reply', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('邮箱').fill('demo-a@arbor.eval')
  await page.getByLabel('密码').fill('arbor-owner')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { level: 1, name: '工作空间' })).toBeVisible()
  await page.getByRole('button', { name: /林夏/ }).click()
  await page.getByLabel('发送消息').fill('你好')
  await page.getByRole('button', { name: '发送' }).click()
  const transcript = page.getByRole('list', { name: '对话记录' })
  await expect(transcript.getByLabel('助手').last()).toBeVisible({ timeout: 30000 })
})

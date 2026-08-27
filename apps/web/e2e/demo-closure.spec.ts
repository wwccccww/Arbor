import { test, expect } from '@playwright/test'

test('林夏：问吵架原因并点引用跳回面店争吵', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('邮箱').fill('demo-a@arbor.eval')
  await page.getByLabel('密码').fill('arbor-owner')
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByRole('button', { name: /林夏/ }).click()

  await page.getByLabel('发送消息').fill('我们上次为什么吵架？')
  await page.getByRole('button', { name: '发送' }).click()

  const transcript = page.getByRole('list', { name: '对话记录' })
  await expect(transcript.getByLabel('助手')).toContainText('香菜', { timeout: 30000 })

  const cite = transcript.getByLabel('助手').getByRole('list', { name: '依据' })
  await expect(cite).toBeVisible()
  await cite.getByRole('button').first().click()

  await expect(page.locator('.biography-tree').getByText('面店争吵', { exact: true })).toBeVisible({
    timeout: 15000,
  })
})

test('客服小周：同问吵架应表现为无知', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('邮箱').fill('demo-a@arbor.eval')
  await page.getByLabel('密码').fill('arbor-owner')
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByRole('button', { name: /客服小周/ }).click()

  await page.getByLabel('发送消息').fill('我们上次为什么吵架？')
  await page.getByRole('button', { name: '发送' }).click()

  const assistant = page.getByRole('list', { name: '对话记录' }).getByLabel('助手')
  await expect(assistant).toBeVisible({ timeout: 30000 })
  await expect(assistant).toContainText(/没有找到|没有.*记忆/)
  await expect(assistant).not.toContainText('老张面馆')
})

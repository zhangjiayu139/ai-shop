// @vitest-environment jsdom
import { createApp } from 'vue'
import { expect, it } from 'vitest'
import { installElement } from './element'

it('registers nested Element components and custom workspace icons', () => {
  const app = createApp({})
  installElement(app)
  for (const name of ['ElTableColumn', 'ElRadioGroup', 'ElDropdownItem', 'ElSelect', 'ElTag', 'Tickets', 'User', 'SwitchButton', 'TopRight']) {
    expect(app.component(name), name).toBeDefined()
  }
  expect(app.directive('loading')).toBeDefined()
})

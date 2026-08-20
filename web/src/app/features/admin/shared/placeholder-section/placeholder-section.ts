import { Component, input } from '@angular/core';

@Component({
  selector: 'situr-placeholder-section',
  imports: [],
  templateUrl: './placeholder-section.html',
  styleUrl: './placeholder-section.css',
})
export class PlaceholderSection {
  readonly title = input.required<string>();
}

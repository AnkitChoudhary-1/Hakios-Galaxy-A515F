// IrisStoriesHeaderView.h - Horizontal stories row component
#import <UIKit/UIKit.h>
#import "IrisData.h"

@protocol IrisStoriesHeaderViewDelegate <NSObject>
- (void)storiesHeaderViewDidSelectStory:(IrisStory *)story;
@end

@interface IrisStoriesHeaderView : UIView

@property (nonatomic, weak) id<IrisStoriesHeaderViewDelegate> delegate;

- (void)reloadStories;
- (void)updateTheme;

@end
